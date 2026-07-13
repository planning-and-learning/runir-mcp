from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from pypddl.formalism import ParserOptions
from pyrunir.datasets import (
    GroundTaskSearchContext,
    LiftedTaskSearchContext,
    StateGraphCostMode,
    StateGraphGenerationOptions,
    annotate_ground_state_graph,
    generate_ground_state_graph_result,
)
from pyrunir.kr import GroundTaskContext
from pyrunir.kr.dl.base.semantics import ConstructorRepositoryFactory as BaseDLRepositoryFactory
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtDLRepositoryFactory
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLRepositoryFactory
from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
from pyrunir.kr.ps.base import (
    GroundSketchSearchOptions,
)
from pyrunir.kr.ps.base import RepositoryFactory as BasePolicyRepositoryFactory
from pyrunir.kr.ps.base import (
    prove_ground_solution as prove_base_solution,
)
from pyrunir.kr.ps.base.dl import SketchFactory, parse_sketch
from pyrunir.kr.ps.ext import (
    GroundModuleProgramSearchOptions,
)
from pyrunir.kr.ps.ext import RepositoryFactory as ExtPolicyRepositoryFactory
from pyrunir.kr.ps.ext import (
    prove_ground_solution as prove_ext_solution,
)
from pyrunir.kr.ps.ext.dl import (
    ModuleProgramStructuralTerminationResult,
    StructuralTerminationStatus,
    parse_module_program,
    structural_termination,
)
from pyrunir.kr.uns import RepositoryFactory as ClassifierRepositoryFactory
from pyrunir.kr.uns import classify
from pyrunir.kr.uns.dl import ClassifierFactory, parse_classifier
from pytyr.formalism.planning import Parser
from pytyr.planning import SearchStatus
from pytyr.planning.lifted import (
    GroundTaskInstantiationOptions,
    GroundTaskInstantiationStatus,
)
from pytyr.planning.lifted import (
    Task as LiftedTask,
)
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.candidates import Candidate, Classifier, ModuleProgram, Policy
from pyrunir_mcp.context import DomainContext, TaskContext
from pyrunir_mcp.defaults import (
    CLASSIFIER_MISTAKE_LIMIT,
    CLASSIFIER_PROOF_BUDGET,
    EXECUTE_SEARCH_BUDGET,
    PLAN_TRACE_BUDGET,
    PROVE_SEARCH_BUDGET,
    SearchBudget,
)
from pyrunir_mcp.enums import (
    AtomKind,
    CandidateSource,
    CounterexampleKind,
    RolloutOutcome,
    ValidationKind,
    ValidationStatus,
)
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.keys import (
    Keys,
)
from pyrunir_mcp.kr.ps.base.core.data_loader import (
    LoadedLiftedSearchContext as BaseLoadedLiftedSearchContext,
)
from pyrunir_mcp.kr.ps.base.core.data_loader import (
    LoadedSearchContext as BaseLoadedSearchTaskContext,
)
from pyrunir_mcp.kr.ps.base.core.features import (
    BasePolicyContext,
)
from pyrunir_mcp.kr.ps.base.core.features import (
    ExecutionFailure as BaseExecutionFailure,
)
from pyrunir_mcp.kr.ps.base.core.features import collect_features as collect_base_policy_features
from pyrunir_mcp.kr.ps.base.rollout import (
    RolloutResult,
    greedy_policy_rollout,
    rollout_category,
    rollout_witness,
)
from pyrunir_mcp.kr.ps.classifier import ClassifierContext, classifier_evidence
from pyrunir_mcp.kr.ps.execute import configure_search_options, rollout_seeds
from pyrunir_mcp.kr.ps.ext.core.features import (
    ExecutionFailure as ExtExecutionFailure,
)
from pyrunir_mcp.kr.ps.ext.core.features import (
    ModuleProgramContext,
)
from pyrunir_mcp.kr.ps.ext.rollout import (
    ExtRolloutResult,
    ext_rollout_category,
    ext_rollout_witness,
    greedy_module_program_rollout,
)
from pyrunir_mcp.kr.ps.ext.rules import collect_features as collect_ext_program_features
from pyrunir_mcp.kr.ps.feature_evidence import AtomEvidence, state_atom_evidence, state_evidence
from pyrunir_mcp.kr.ps.proof import (
    FailureWitness,
    ProofResult,
    ProofStatus,
    StateEvidence,
    failure_items,
    make_search_options,
    state_summary,
)
from pyrunir_mcp.kr.uns.serialize import feature_values as classifier_feature_values
from pyrunir_mcp.planning import parse_task_file


@dataclass(frozen=True, slots=True)
class ClassifierProofCounts:
    states: int
    unsolvable: int
    false_positive: int
    false_negative: int


@dataclass(frozen=True, slots=True)
class ClassifierMistake:
    id: str
    category: str
    state: int
    features: JsonObject
    fluent: tuple[str, ...]
    derived: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FailureFingerprint:
    kind: ValidationKind
    status: ValidationStatus
    problem_file: str | None
    category: str
    witness: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecuteObservationDetails:
    failure_problem_file: str | None
    failure_status: object | None
    num_rollouts: int


@dataclass(frozen=True, slots=True)
class ProofObservationDetails:
    proof_status: ProofStatus
    successful: bool


@dataclass(frozen=True, slots=True)
class ClassifierObservationDetails:
    counts: ClassifierProofCounts
    state_graph_status: SearchStatus | None = None


@dataclass(frozen=True, slots=True)
class TerminationObservationDetails:
    program_status: StructuralTerminationStatus
    terminating: bool
    nonterminating_modules: tuple[str, ...] = ()


ObservationDetails: TypeAlias = (
    ExecuteObservationDetails
    | ProofObservationDetails
    | ClassifierObservationDetails
    | TerminationObservationDetails
)


@dataclass(frozen=True, slots=True)
class ValidationObservation:
    result_id: str
    kind: ValidationKind
    status: ValidationStatus
    candidate_id: str
    classifier_id: str | None
    details: ObservationDetails
    fingerprint: FailureFingerprint | None = None


ExecutionFailure: TypeAlias = BaseExecutionFailure | ExtExecutionFailure


def _required_budget_values(budget: SearchBudget, *, name: str) -> tuple[int, float]:
    if budget.max_num_states is None or budget.max_time_seconds is None:
        raise ValueError(f"{name} requires max_num_states and max_time_seconds")
    return budget.max_num_states, budget.max_time_seconds


@dataclass(frozen=True, slots=True)
class ExecutePolicyResult:
    id: str
    kind: ValidationKind
    status: ValidationStatus
    context: TaskContext
    candidate: Policy
    observation: ValidationObservation
    classifier: Classifier | None
    failure: BaseExecutionFailure | None
    successful_results: tuple[tuple[int, ProofResult], ...]
    num_rollouts: int
    failure_results: tuple[tuple[int, BaseExecutionFailure], ...] = ()
    search_budget: SearchBudget = EXECUTE_SEARCH_BUDGET
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET
    rollout_results: tuple[tuple[int, RolloutResult], ...] = ()


@dataclass(frozen=True, slots=True)
class ExecuteModuleProgramResult:
    id: str
    kind: ValidationKind
    status: ValidationStatus
    context: TaskContext
    candidate: ModuleProgram
    observation: ValidationObservation
    classifier: Classifier | None
    failure: ExtExecutionFailure | None
    successful_results: tuple[tuple[int, ProofResult], ...]
    num_rollouts: int
    failure_results: tuple[tuple[int, ExtExecutionFailure], ...] = ()
    search_budget: SearchBudget = EXECUTE_SEARCH_BUDGET
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET
    rollout_results: tuple[tuple[int, ExtRolloutResult], ...] = ()


@dataclass(frozen=True, slots=True)
class ProvePolicyResult:
    id: str
    kind: ValidationKind
    status: ValidationStatus
    context: TaskContext
    candidate: Policy
    observation: ValidationObservation
    evidence_classifier: Classifier | None
    proof: ProofResult
    search_budget: SearchBudget = PROVE_SEARCH_BUDGET
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET


@dataclass(frozen=True, slots=True)
class ProveModuleProgramResult:
    id: str
    kind: ValidationKind
    status: ValidationStatus
    context: TaskContext
    candidate: ModuleProgram
    observation: ValidationObservation
    evidence_classifier: Classifier | None
    proof: ProofResult
    search_budget: SearchBudget = PROVE_SEARCH_BUDGET
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET


@dataclass(frozen=True, slots=True)
class ProveClassifierResult:
    id: str
    kind: ValidationKind
    status: ValidationStatus
    context: TaskContext
    candidate: Classifier
    observation: ValidationObservation
    counts: ClassifierProofCounts
    mistakes: tuple[ClassifierMistake, ...] = ()
    atoms: tuple[AtomEvidence, ...] = ()
    search_budget: SearchBudget = CLASSIFIER_PROOF_BUDGET


@dataclass(frozen=True, slots=True)
class ProveTerminationResult:
    id: str
    kind: ValidationKind
    status: ValidationStatus
    domain_context: DomainContext
    candidate: ModuleProgram
    observation: ValidationObservation
    program_result: ModuleProgramStructuralTerminationResult
    nonterminating_modules: tuple[str, ...] = ()


ValidationResult: TypeAlias = (
    ExecutePolicyResult
    | ExecuteModuleProgramResult
    | ProvePolicyResult
    | ProveModuleProgramResult
    | ProveClassifierResult
    | ProveTerminationResult
)

def create_domain_context(domain_file: str | Path) -> DomainContext:
    domain_path = Path(domain_file).resolve()
    parser = Parser(domain_path, ParserOptions())
    planning_domain = parser.get_domain()
    base_dl_repository = BaseDLRepositoryFactory().create(planning_domain)
    ext_dl_repository = ExtDLRepositoryFactory().create(planning_domain)
    classifier_context = ClassifierContext(
        planning_domain=planning_domain,
        classifier_repository=ClassifierRepositoryFactory().create(
            UnsDLRepositoryFactory().create(planning_domain)
        ),
    )
    return DomainContext(
        id="domain_000001",
        domain_file=domain_path,
        parser=parser,
        planning_domain=planning_domain,
        base_policy_context=BasePolicyContext(
            planning_domain=planning_domain,
            dl_repository=base_dl_repository,
            policy_repository=BasePolicyRepositoryFactory().create(base_dl_repository),
        ),
        module_program_context=ModuleProgramContext(
            planning_domain=planning_domain,
            module_output_repository=ext_dl_repository,
            policy_repository=ExtPolicyRepositoryFactory().create(ext_dl_repository),
        ),
        classifier_context=classifier_context,
    )


def create_task_context(
    domain_context: DomainContext, problem_file: str | Path, *, num_threads: int = 1
) -> TaskContext:
    problem_path = Path(problem_file).resolve()
    index = domain_context.next_task_index
    domain_context.next_task_index += 1
    execution_context = ExecutionContext(num_threads)
    formalism_task = parse_task_file(domain_context.parser, problem_path, ParserOptions())
    lifted_task = LiftedTask(formalism_task)
    lifted_context = LiftedTaskSearchContext(lifted_task, execution_context)
    grounded = lifted_task.instantiate_ground_task(
        execution_context, GroundTaskInstantiationOptions()
    )
    if grounded.status != GroundTaskInstantiationStatus.SUCCESS:
        raise RuntimeError(f"Grounding failed for {problem_path}: {grounded.status}")
    ground_search_context = GroundTaskSearchContext(grounded.task, execution_context)
    ground_task_context = GroundTaskContext(ground_search_context)
    loaded_ground_context = BaseLoadedSearchTaskContext(
        problem_path=problem_path, task_context=ground_task_context
    )
    loaded_lifted_context = BaseLoadedLiftedSearchContext(
        problem_path=problem_path, search_context=lifted_context
    )
    return TaskContext(
        id=f"task_{index:06d}",
        domain_context=domain_context,
        index=index,
        problem_file=problem_path,
        execution_context=execution_context,
        base_task=loaded_ground_context,
        base_lifted_task=loaded_lifted_context,
        ext_task=loaded_ground_context,
        ext_lifted_task=loaded_lifted_context,
    )


def create_policy(domain_context: DomainContext, policy_file: str | Path | None) -> Policy:
    index = domain_context.next_policy_index
    domain_context.next_policy_index += 1
    if policy_file is None:
        return Policy(
            id=f"policy_{index:06d}",
            value=SketchFactory.create_empty(domain_context.base_policy_context.policy_repository),
            source=CandidateSource.EMPTY,
        )
    path = Path(policy_file).resolve()
    return Policy(
        id=f"policy_{index:06d}",
        value=parse_sketch(
            path.read_text(encoding="utf-8").lstrip(),
            domain_context.base_policy_context.planning_domain,
            domain_context.base_policy_context.policy_repository,
        ),
        source=CandidateSource.FILE,
        source_file=path,
    )




def write_empty_policy(domain_context: DomainContext, policy_file: str | Path) -> Policy:
    policy = create_policy(domain_context, None)
    path = Path(policy_file).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(policy.value).rstrip() + "\n", encoding="utf-8")
    return Policy(
        id=policy.id,
        value=policy.value,
        source=CandidateSource.FILE,
        source_file=path,
    )

def create_module_program(
    domain_context: DomainContext, module_program_file: str | Path | None
) -> ModuleProgram:
    index = domain_context.next_module_program_index
    domain_context.next_module_program_index += 1
    if module_program_file is None:
        text = """(:program
    (:entry empty)
    (:module
        (:symbol empty)
        (:arguments)
        (:registers)
        (:entry m0)
        (:memory m0)
        (:features)
        (:rules)
    )
)"""
        source = CandidateSource.EMPTY
        source_file = None
    else:
        source_file = Path(module_program_file).resolve()
        text = source_file.read_text(encoding="utf-8")
        source = CandidateSource.FILE
    return ModuleProgram(
        id=f"module_program_{index:06d}",
        value=parse_module_program(
            text.lstrip(),
            domain_context.module_program_context.planning_domain,
            domain_context.module_program_context.policy_repository,
        ),
        source=source,
        source_file=source_file,
    )


def create_classifier(
    domain_context: DomainContext, classifier_file: str | Path | None
) -> Classifier:
    index = domain_context.next_classifier_index
    domain_context.next_classifier_index += 1
    if classifier_file is None:
        return Classifier(
            id=f"classifier_{index:06d}",
            value=ClassifierFactory.create_empty(
                domain_context.classifier_context.classifier_repository
            ),
            source=CandidateSource.EMPTY,
        )
    path = Path(classifier_file).resolve()
    return Classifier(
        id=f"classifier_{index:06d}",
        value=parse_classifier(
            path.read_text(encoding="utf-8").lstrip(),
            domain_context.classifier_context.planning_domain,
            domain_context.classifier_context.classifier_repository,
        ),
        source=CandidateSource.FILE,
        source_file=path,
    )


def _next_result_id(domain_context: DomainContext) -> str:
    index = domain_context.next_result_index
    domain_context.next_result_index += 1
    return f"result_{index:06d}"



def _execute_rollout_details(
    context: TaskContext, first_failure: RolloutResult | None, num_rollouts: int
) -> ExecuteObservationDetails:
    if first_failure is None:
        return ExecuteObservationDetails(
            failure_problem_file=None,
            failure_status=None,
            num_rollouts=num_rollouts,
        )
    return ExecuteObservationDetails(
        failure_problem_file=context.base_task.problem_path.name,
        failure_status=rollout_category(first_failure),
        num_rollouts=num_rollouts,
    )


def _execute_rollout_fingerprint(
    *,
    kind: ValidationKind,
    status: ValidationStatus,
    context: TaskContext,
    first_failure: RolloutResult | None,
) -> FailureFingerprint | None:
    if first_failure is None or status is ValidationStatus.SUCCESS:
        return None
    category = rollout_category(first_failure)
    if category is None:
        return None
    return FailureFingerprint(
        kind=kind,
        status=status,
        problem_file=context.base_task.problem_path.name,
        category=category,
        witness=rollout_witness(first_failure),
    )



def _execute_ext_rollout_details(
    context: TaskContext, first_failure: ExtRolloutResult | None, num_rollouts: int
) -> ExecuteObservationDetails:
    if first_failure is None:
        return ExecuteObservationDetails(
            failure_problem_file=None,
            failure_status=None,
            num_rollouts=num_rollouts,
        )
    return ExecuteObservationDetails(
        failure_problem_file=context.ext_task.problem_path.name,
        failure_status=ext_rollout_category(first_failure),
        num_rollouts=num_rollouts,
    )


def _execute_ext_rollout_fingerprint(
    *,
    kind: ValidationKind,
    status: ValidationStatus,
    context: TaskContext,
    first_failure: ExtRolloutResult | None,
) -> FailureFingerprint | None:
    if first_failure is None or status is ValidationStatus.SUCCESS:
        return None
    category = ext_rollout_category(first_failure)
    if category is None:
        return None
    return FailureFingerprint(
        kind=kind,
        status=status,
        problem_file=context.ext_task.problem_path.name,
        category=category,
        witness=ext_rollout_witness(first_failure),
    )

def _proof_details(proof: ProofResult) -> ProofObservationDetails:
    return ProofObservationDetails(
        proof_status=proof.status,
        successful=bool(proof.is_successful()),
    )


def _state_id_for_vertex(proof: ProofResult, vertex: int) -> str:
    graph = getattr(proof, "graph", None)
    if graph is None:
        return f"s{int(vertex)}"
    try:
        state_index = state_summary(graph, int(vertex))[Keys.STATE_INDEX]
    except Exception:
        return f"s{int(vertex)}"
    if isinstance(state_index, int | str | float):
        return f"s{int(state_index)}"
    return f"s{int(vertex)}"


def _state_id_for_deadend_transition(proof: ProofResult, edge: int) -> str:
    graph = getattr(proof, "graph", None)
    if graph is None:
        return str(int(edge))
    try:
        return _state_id_for_vertex(proof, int(graph.get_target(int(edge))))
    except Exception:
        return str(int(edge))


def _state_id_key(value: str) -> tuple[int, str]:
    suffix = value[1:] if value.startswith("s") else value
    try:
        return (int(suffix), value)
    except ValueError:
        return (0, value)


def _cycle_part_key(value: str) -> tuple[tuple[int, str], tuple[int, str], tuple[int, str]]:
    parts = value.split("|", 2)
    if len(parts) == 3:
        module, memory, state = parts
        return ((0, module), (0, memory), _state_id_key(state))
    return ((0, ""), (0, ""), _state_id_key(value))


def rotate_smallest_state_id_first(state_ids: list[str]) -> tuple[str, ...]:
    if not state_ids:
        return ()
    closed = len(state_ids) > 1 and state_ids[0] == state_ids[-1]
    ring = state_ids[:-1] if closed else state_ids
    start = min(range(len(ring)), key=lambda index: _cycle_part_key(ring[index]))
    rotated = tuple(ring[start:] + ring[:start])
    return (*rotated, rotated[0]) if closed and rotated else rotated


def _cycle_vertex_part(proof: ProofResult, vertex: int) -> str:
    graph = getattr(proof, "graph", None)
    if graph is None:
        return f"s{int(vertex)}"
    try:
        summary = state_summary(graph, int(vertex))
    except Exception:
        return f"s{int(vertex)}"
    state_index = summary.get(Keys.STATE_INDEX)
    state = f"s{int(state_index)}" if isinstance(state_index, int | str | float) else f"s{int(vertex)}"
    module = summary.get(Keys.MODULE)
    memory = summary.get(Keys.MEMORY)
    if isinstance(module, str) and isinstance(memory, str):
        return f"{module}|{memory}|{state}"
    return state


def _witness_parts(
    *, proof: ProofResult, category: CounterexampleKind, witness: FailureWitness
) -> tuple[str, ...]:
    if category is CounterexampleKind.CYCLE and isinstance(witness, list):
        return rotate_smallest_state_id_first(
            [_cycle_vertex_part(proof, int(vertex)) for vertex in witness]
        )
    if category is CounterexampleKind.DEADEND_TRANSITION and not isinstance(witness, list):
        return (_state_id_for_deadend_transition(proof, int(witness)),)
    if isinstance(witness, list):
        return tuple(_state_id_for_vertex(proof, int(vertex)) for vertex in witness)
    return (_state_id_for_vertex(proof, int(witness)),)


def _proof_fingerprint(
    *,
    kind: ValidationKind,
    status: ValidationStatus,
    problem_file: str | None,
    proof: ProofResult,
    evidence: StateEvidence | None = None,
) -> FailureFingerprint | None:
    if status is ValidationStatus.SUCCESS:
        return None
    items = failure_items(
        proof,
        max_open_state_counterexamples=1,
        max_deadend_transition_counterexamples=1,
        evidence=evidence,
    )
    if items:
        category, witness = items[0]
        return FailureFingerprint(
            kind=kind,
            status=status,
            problem_file=problem_file,
            category=category.value,
            witness=_witness_parts(proof=proof, category=category, witness=witness),
        )
    return FailureFingerprint(
        kind=kind,
        status=status,
        problem_file=problem_file,
        category=proof.status.name.lower(),
    )



def _classifier_fingerprint(
    *,
    kind: ValidationKind,
    status: ValidationStatus,
    problem_file: str | None,
    counts: ClassifierProofCounts,
    state_graph_status: SearchStatus | None = None,
) -> FailureFingerprint | None:
    if status is ValidationStatus.SUCCESS:
        return None
    category = state_graph_status.name.lower() if state_graph_status is not None else "misclassified_states"
    return FailureFingerprint(
        kind=kind,
        status=status,
        problem_file=problem_file,
        category=category,
        witness=(
            f"states={counts.states}",
            f"unsolvable={counts.unsolvable}",
            f"fp={counts.false_positive}",
            f"fn={counts.false_negative}",
        ),
    )


def _classifier_json_features(values: dict[str, bool]) -> JsonObject:
    return {key: value for key, value in values.items()}


def _classifier_details(
    counts: ClassifierProofCounts,
    *,
    state_graph_status: SearchStatus | None = None,
) -> ClassifierObservationDetails:
    return ClassifierObservationDetails(
        counts=counts,
        state_graph_status=state_graph_status,
    )


def _base_classifier_evidence(
    task_context: GroundTaskContext,
    policy: Policy,
    classifier: Classifier | None,
) -> StateEvidence | None:
    if classifier is None:
        return None
    features = collect_base_policy_features(policy.value)
    return classifier_evidence(
        task_context,
        state_evidence(
            task_context,
            features,
            include_facts=True,
            include_hstar=False,
            include_hlmcut=False,
        ),
        classifier.value,
    )


def _ext_classifier_evidence(
    task_context: GroundTaskContext,
    module_program: ModuleProgram,
    classifier: Classifier | None,
) -> StateEvidence | None:
    if classifier is None:
        return None
    features = collect_ext_program_features(module_program.value)
    return classifier_evidence(
        task_context,
        state_evidence(
            task_context,
            features,
            include_facts=True,
            include_hstar=False,
            include_hlmcut=False,
        ),
        classifier.value,
    )


def _validation_observation(
    *,
    result_id: str,
    kind: ValidationKind,
    status: ValidationStatus,
    candidate: Candidate,
    classifier: Classifier | None,
    details: ObservationDetails,
    fingerprint: FailureFingerprint | None = None,
) -> ValidationObservation:
    return ValidationObservation(
        result_id=result_id,
        kind=kind,
        status=status,
        candidate_id=candidate.id,
        classifier_id=classifier.id if classifier is not None else None,
        details=details,
        fingerprint=fingerprint,
    )


def execute_policy(
    context: TaskContext,
    policy: Policy,
    *,
    classifier: Classifier | None = None,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    max_arity: int = 0,
    search_budget: SearchBudget = EXECUTE_SEARCH_BUDGET,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ExecutePolicyResult:
    del max_arity
    classifier_value = (
        classifier.value
        if classifier is not None
        else ClassifierFactory.create_empty(
            context.domain_context.classifier_context.classifier_repository
        )
    )
    rollout_results: list[tuple[int, RolloutResult]] = []
    first_failure: RolloutResult | None = None
    max_steps = search_budget.max_num_states
    for seed in rollout_seeds(num_rollouts, random_seed, random_seed_start):
        rollout = greedy_policy_rollout(
            context.base_task.task_context,
            policy.value,
            classifier_value,
            max_steps=max_steps if max_steps is not None else 1_000_000,
            random_seed=seed,
            shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
        )
        rollout_results.append((seed, rollout))
        if rollout.outcome is not RolloutOutcome.GOAL and first_failure is None:
            first_failure = rollout
    status = ValidationStatus.SUCCESS if first_failure is None else ValidationStatus.FAILURE
    result_id = _next_result_id(context.domain_context)
    details = _execute_rollout_details(context, first_failure, num_rollouts)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.BASE_EXECUTE,
        status=status,
        candidate=policy,
        classifier=classifier,
        details=details,
        fingerprint=_execute_rollout_fingerprint(
            kind=ValidationKind.BASE_EXECUTE,
            status=status,
            context=context,
            first_failure=first_failure,
        ),
    )
    return ExecutePolicyResult(
        id=result_id,
        kind=ValidationKind.BASE_EXECUTE,
        status=status,
        context=context,
        candidate=policy,
        observation=observation,
        classifier=classifier,
        failure=None,
        successful_results=(),
        num_rollouts=num_rollouts,
        failure_results=(),
        search_budget=search_budget,
        plan_trace_budget=plan_trace_budget,
        rollout_results=tuple(rollout_results),
    )


def execute_module_program(
    context: TaskContext,
    module_program: ModuleProgram,
    *,
    classifier: Classifier | None = None,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    max_arity: int = 0,
    search_budget: SearchBudget = EXECUTE_SEARCH_BUDGET,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ExecuteModuleProgramResult:
    classifier_value = (
        classifier.value
        if classifier is not None
        else ClassifierFactory.create_empty(
            context.domain_context.classifier_context.classifier_repository
        )
    )
    rollout_results: list[tuple[int, ExtRolloutResult]] = []
    first_failure: ExtRolloutResult | None = None
    for seed in rollout_seeds(num_rollouts, random_seed, random_seed_start):
        options = configure_search_options(
            GroundModuleProgramSearchOptions(),
            random_seed=seed,
            shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
            max_arity=max_arity,
            max_num_states=search_budget.max_num_states,
            max_time_seconds=search_budget.max_time_seconds,
        )
        rollout = greedy_module_program_rollout(
            context.ext_task.task_context,
            module_program.value,
            classifier_value,
            options,
            max_steps=search_budget.max_num_states or 1_000_000,
        )
        rollout_results.append((seed, rollout))
        if ext_rollout_category(rollout) is not None and first_failure is None:
            first_failure = rollout
    status = ValidationStatus.SUCCESS if first_failure is None else ValidationStatus.FAILURE
    result_id = _next_result_id(context.domain_context)
    details = _execute_ext_rollout_details(context, first_failure, num_rollouts)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.EXT_EXECUTE,
        status=status,
        candidate=module_program,
        classifier=classifier,
        details=details,
        fingerprint=_execute_ext_rollout_fingerprint(
            kind=ValidationKind.EXT_EXECUTE,
            status=status,
            context=context,
            first_failure=first_failure,
        ),
    )
    return ExecuteModuleProgramResult(
        result_id,
        ValidationKind.EXT_EXECUTE,
        status,
        context,
        module_program,
        observation,
        classifier,
        None,
        (),
        num_rollouts,
        (),
        search_budget,
        plan_trace_budget,
        tuple(rollout_results),
    )


def prove_policy(
    context: TaskContext,
    policy: Policy,
    *,
    evidence_classifier: Classifier | None = None,
    search_budget: SearchBudget = PROVE_SEARCH_BUDGET,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ProvePolicyResult:
    max_num_states, max_time_seconds = _required_budget_values(
        search_budget, name="prove_policy search_budget"
    )
    proof = prove_base_solution(
        context.base_task.task_context,
        policy.value,
        make_search_options(GroundSketchSearchOptions(), max_num_states, max_time_seconds),
    )
    status = ValidationStatus.SUCCESS if proof.is_successful() else ValidationStatus.FAILURE
    result_id = _next_result_id(context.domain_context)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.BASE_PROVE,
        status=status,
        candidate=policy,
        classifier=evidence_classifier,
        details=_proof_details(proof),
        fingerprint=_proof_fingerprint(
            kind=ValidationKind.BASE_PROVE,
            status=status,
            problem_file=context.problem_file.name,
            proof=proof,
            evidence=_base_classifier_evidence(
                context.base_task.task_context, policy, evidence_classifier
            ),
        ),
    )
    return ProvePolicyResult(
        result_id,
        ValidationKind.BASE_PROVE,
        status,
        context,
        policy,
        observation,
        evidence_classifier,
        proof,
        search_budget,
        plan_trace_budget,
    )


def prove_module_program(
    context: TaskContext,
    module_program: ModuleProgram,
    *,
    evidence_classifier: Classifier | None = None,
    search_budget: SearchBudget = PROVE_SEARCH_BUDGET,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
    max_arity: int = 0,
) -> ProveModuleProgramResult:
    max_num_states, max_time_seconds = _required_budget_values(
        search_budget, name="prove_module_program search_budget"
    )
    options = make_search_options(
        GroundModuleProgramSearchOptions(), max_num_states, max_time_seconds
    )
    options.max_arity = max_arity
    proof = prove_ext_solution(context.ext_task.task_context, module_program.value, options)
    status = ValidationStatus.SUCCESS if proof.is_successful() else ValidationStatus.FAILURE
    result_id = _next_result_id(context.domain_context)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.EXT_PROVE,
        status=status,
        candidate=module_program,
        classifier=evidence_classifier,
        details=_proof_details(proof),
        fingerprint=_proof_fingerprint(
            kind=ValidationKind.EXT_PROVE,
            status=status,
            problem_file=context.problem_file.name,
            proof=proof,
            evidence=_ext_classifier_evidence(
                context.ext_task.task_context, module_program, evidence_classifier
            ),
        ),
    )
    return ProveModuleProgramResult(
        result_id,
        ValidationKind.EXT_PROVE,
        status,
        context,
        module_program,
        observation,
        evidence_classifier,
        proof,
        search_budget,
        plan_trace_budget,
    )



def _module_names(module_program: ModuleProgram) -> tuple[str, ...]:
    names: list[str] = []
    for index, module in enumerate(module_program.value.get_modules()):
        get_name = getattr(module, "get_name", None)
        if callable(get_name):
            names.append(str(get_name()))
        else:
            names.append(f"module_{index}")
    return tuple(names)


def _termination_observation_details(
    program_result: ModuleProgramStructuralTerminationResult,
    nonterminating_modules: tuple[str, ...],
) -> TerminationObservationDetails:
    return TerminationObservationDetails(
        program_status=program_result.status,
        terminating=bool(program_result.is_terminating()),
        nonterminating_modules=nonterminating_modules,
    )


def _termination_fingerprint(
    *,
    status: ValidationStatus,
    program_result: ModuleProgramStructuralTerminationResult,
    nonterminating_modules: tuple[str, ...],
) -> FailureFingerprint | None:
    if status is ValidationStatus.SUCCESS:
        return None
    return FailureFingerprint(
        kind=ValidationKind.EXT_TERMINATION,
        status=status,
        problem_file=None,
        category="structural_termination",
        witness=(program_result.status.name.lower(), *nonterminating_modules),
    )


def prove_termination(
    domain_context: DomainContext,
    module_program: ModuleProgram,
    *,
    max_features: int,
    use_incomplete_preprocessing: bool,
) -> ProveTerminationResult:
    program_result = structural_termination(
        module_program.value,
        max_features=max_features,
        use_incomplete_preprocessing=use_incomplete_preprocessing,
    )
    module_names = _module_names(module_program)
    module_results = tuple(program_result.module_results)
    nonterminating_modules = tuple(
        module_names[index] if index < len(module_names) else f"module_{index}"
        for index, module_result in enumerate(module_results)
        if not bool(module_result.is_terminating())
    )
    status = (
        ValidationStatus.SUCCESS
        if bool(program_result.is_terminating())
        else ValidationStatus.FAILURE
    )
    result_id = _next_result_id(domain_context)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.EXT_TERMINATION,
        status=status,
        candidate=module_program,
        classifier=None,
        details=_termination_observation_details(program_result, nonterminating_modules),
        fingerprint=_termination_fingerprint(
            status=status,
            program_result=program_result,
            nonterminating_modules=nonterminating_modules,
        ),
    )
    return ProveTerminationResult(
        result_id,
        ValidationKind.EXT_TERMINATION,
        status,
        domain_context,
        module_program,
        observation,
        program_result,
        nonterminating_modules=nonterminating_modules,
    )


def prove_classifier(
    context: TaskContext,
    classifier: Classifier,
    *,
    search_budget: SearchBudget = CLASSIFIER_PROOF_BUDGET,
    max_mistakes_per_category: int = CLASSIFIER_MISTAKE_LIMIT,
) -> ProveClassifierResult:
    generation_options = StateGraphGenerationOptions()
    if search_budget.max_num_states is not None:
        generation_options.max_num_states = search_budget.max_num_states
    if search_budget.max_time_seconds is not None:
        generation_options.max_time = search_budget.max_time_seconds
    graph_result = generate_ground_state_graph_result(
        context.base_task.search_context, generation_options
    )
    if graph_result.status != SearchStatus.EXHAUSTED:
        counts = ClassifierProofCounts(states=0, unsolvable=0, false_positive=0, false_negative=0)
        result_id = _next_result_id(context.domain_context)
        details = _classifier_details(counts, state_graph_status=graph_result.status)
        observation = _validation_observation(
            result_id=result_id,
            kind=ValidationKind.UNS_PROVE,
            status=ValidationStatus.FAILURE,
            candidate=classifier,
            classifier=None,
            details=details,
            fingerprint=_classifier_fingerprint(
                kind=ValidationKind.UNS_PROVE,
                status=ValidationStatus.FAILURE,
                problem_file=context.problem_file.name,
                counts=counts,
                state_graph_status=graph_result.status,
            ),
        )
        return ProveClassifierResult(
            result_id,
            ValidationKind.UNS_PROVE,
            ValidationStatus.FAILURE,
            context,
            classifier,
            observation,
            counts,
            search_budget=search_budget,
        )

    graph = annotate_ground_state_graph(
        context.base_task.search_context, graph_result.graph, StateGraphCostMode.UNIT_COST
    ).get_forward_graph()
    builder = context.base_task.task_context.dl_builder
    denotations = context.base_task.task_context.dl_denotation_repository
    states = 0
    unsolvable = 0
    false_positive = 0
    false_negative = 0
    mistakes: list[ClassifierMistake] = []
    fluent_atoms: set[str] = set()
    derived_atoms: set[str] = set()
    for vertex in graph.get_vertex_indices():
        states += 1
        label = graph.get_vertex_property(vertex)
        actually_solvable = not bool(label.is_unsolvable)
        if not actually_solvable:
            unsolvable += 1
        state_atoms = state_atom_evidence(label.state)
        fluent_atoms.update(state_atoms[AtomKind.FLUENT])
        derived_atoms.update(state_atoms[AtomKind.DERIVED])
        eval_context = GroundEvaluationContext(label.state, builder, denotations)
        predicted_unsolvable = bool(classify(classifier.value, eval_context))
        if predicted_unsolvable and actually_solvable:
            false_positive += 1
            if false_positive <= max_mistakes_per_category:
                mistakes.append(
                    ClassifierMistake(
                        id=f"false_positive-{false_positive:03d}",
                        category="false_positive",
                        state=int(label.state.get_index()),
                        features=_classifier_json_features(classifier_feature_values(classifier.value, eval_context)),
                        fluent=state_atoms[AtomKind.FLUENT],
                        derived=state_atoms[AtomKind.DERIVED],
                    )
                )
        elif not predicted_unsolvable and not actually_solvable:
            false_negative += 1
            if false_negative <= max_mistakes_per_category:
                mistakes.append(
                    ClassifierMistake(
                        id=f"false_negative-{false_negative:03d}",
                        category="false_negative",
                        state=int(label.state.get_index()),
                        features=_classifier_json_features(classifier_feature_values(classifier.value, eval_context)),
                        fluent=state_atoms[AtomKind.FLUENT],
                        derived=state_atoms[AtomKind.DERIVED],
                    )
                )
    counts = ClassifierProofCounts(
        states=states,
        unsolvable=unsolvable,
        false_positive=false_positive,
        false_negative=false_negative,
    )
    status = (
        ValidationStatus.SUCCESS
        if false_positive == 0 and false_negative == 0
        else ValidationStatus.FAILURE
    )
    result_id = _next_result_id(context.domain_context)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.UNS_PROVE,
        status=status,
        candidate=classifier,
        classifier=None,
        details=_classifier_details(counts),
        fingerprint=_classifier_fingerprint(
            kind=ValidationKind.UNS_PROVE,
            status=status,
            problem_file=context.problem_file.name,
            counts=counts,
        ),
    )
    return ProveClassifierResult(
        result_id,
        ValidationKind.UNS_PROVE,
        status,
        context,
        classifier,
        observation,
        counts,
        mistakes=tuple(mistakes),
        atoms=(
            *((AtomKind.FLUENT, atom) for atom in sorted(fluent_atoms)),
            *((AtomKind.DERIVED, atom) for atom in sorted(derived_atoms)),
        ),
        search_budget=search_budget,
    )
