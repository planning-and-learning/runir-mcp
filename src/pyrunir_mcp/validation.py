from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from enum import StrEnum
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
from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory
from pyrunir.kr.dl.base.semantics import ConstructorRepositoryFactory as BaseDLRepositoryFactory
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtDLRepositoryFactory
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLRepositoryFactory
from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
from pyrunir.kr.ps.base import (
    GroundSketchSearchOptions,
    find_ground_solution as find_base_solution,
    prove_ground_solution as prove_base_solution,
)
from pyrunir.kr.ps.base import RepositoryFactory as BasePolicyRepositoryFactory
from pyrunir.kr.ps.base.dl import SketchFactory, parse_sketch
from pyrunir.kr.ps.ext import (
    GroundModuleProgramSearchOptions,
    find_ground_solution as find_ext_solution,
    parse_module_program,
    prove_ground_solution as prove_ext_solution,
)
from pyrunir.kr.ps.ext import RepositoryFactory as ExtPolicyRepositoryFactory
from pyrunir.kr.uns import RepositoryFactory as ClassifierRepositoryFactory
from pyrunir.kr.uns import classify
from pyrunir.kr.uns.dl import ClassifierFactory, parse_classifier
from pyyggdrasil.execution import ExecutionContext
from pytyr.formalism.planning import Parser
from pytyr.planning import SearchStatus
from pytyr.planning.lifted import (
    GroundTaskInstantiationOptions,
    GroundTaskInstantiationStatus,
    Task as LiftedTask,
)

from pyrunir_mcp.candidates import Candidate, CandidateSource, Classifier, ModuleProgram, Policy
from pyrunir_mcp.context import DomainContext, TaskContext
from pyrunir_mcp.kr.ps.base.core.data_loader import (
    LoadedLiftedSearchContext as BaseLoadedLiftedSearchContext,
)
from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext as BaseLoadedSearchTaskContext
from pyrunir_mcp.kr.ps.base.core.features import (
    BasePolicyContext,
    ExecutionFailure as BaseExecutionFailure,
)
from pyrunir_mcp.kr.ps.execute import configure_search_options, rollout_seeds
from pyrunir_mcp.kr.ps.ext.core.data_loader import (
    LoadedLiftedSearchContext as ExtLoadedLiftedSearchContext,
)
from pyrunir_mcp.kr.ps.ext.core.data_loader import LoadedSearchContext as ExtLoadedSearchTaskContext
from pyrunir_mcp.kr.ps.ext.core.features import (
    ExecutionFailure as ExtExecutionFailure,
    ModuleProgramContext,
)
from pyrunir_mcp.kr.ps.classifier import ClassifierContext
from pyrunir_mcp.kr.ps.status import is_success_status
from pyrunir_mcp.kr.ps.proof import (
    CounterexampleKind,
    FailureWitness,
    ProofResult,
    ProofStatus,
    failure_items,
    is_goal_open_state_result,
    make_search_options,
    state_summary,
)
from pyrunir_mcp.planning import parse_task_file


class ValidationKind(StrEnum):
    BASE_EXECUTE = "base_execute"
    BASE_PROVE = "base_prove"
    EXT_EXECUTE = "ext_execute"
    EXT_PROVE = "ext_prove"
    UNS_PROVE = "uns_prove"


@dataclass(frozen=True, slots=True)
class ClassifierProofCounts:
    states: int
    unsolvable: int
    false_positive: int
    false_negative: int


class ValidationStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


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


ObservationDetails: TypeAlias = (
    ExecuteObservationDetails | ProofObservationDetails | ClassifierObservationDetails
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


@dataclass(frozen=True, slots=True)
class SearchBudget:
    max_num_states: int | None
    max_time_seconds: float | None


PLAN_TRACE_BUDGET = SearchBudget(max_num_states=1_000_000, max_time_seconds=10.0)


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
    search_budget: SearchBudget = SearchBudget(max_num_states=None, max_time_seconds=None)
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET


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
    search_budget: SearchBudget = SearchBudget(max_num_states=None, max_time_seconds=None)
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET


@dataclass(frozen=True, slots=True)
class ProvePolicyResult:
    id: str
    kind: ValidationKind
    status: ValidationStatus
    context: TaskContext
    candidate: Policy
    observation: ValidationObservation
    proof: ProofResult
    search_budget: SearchBudget = SearchBudget(max_num_states=100_000, max_time_seconds=5.0)
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET


@dataclass(frozen=True, slots=True)
class ProveModuleProgramResult:
    id: str
    kind: ValidationKind
    status: ValidationStatus
    context: TaskContext
    candidate: ModuleProgram
    observation: ValidationObservation
    proof: ProofResult
    search_budget: SearchBudget = SearchBudget(max_num_states=100_000, max_time_seconds=5.0)
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


ValidationResult: TypeAlias = (
    ExecutePolicyResult
    | ExecuteModuleProgramResult
    | ProvePolicyResult
    | ProveModuleProgramResult
    | ProveClassifierResult
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
    ground_context = GroundTaskSearchContext(grounded.task, execution_context)
    return TaskContext(
        id=f"task_{index:06d}",
        domain_context=domain_context,
        index=index,
        problem_file=problem_path,
        execution_context=execution_context,
        base_task=BaseLoadedSearchTaskContext(
            problem_path=problem_path, search_context=ground_context
        ),
        base_lifted_task=BaseLoadedLiftedSearchContext(
            problem_path=problem_path, search_context=lifted_context
        ),
        ext_task=ExtLoadedSearchTaskContext(
            problem_path=problem_path, search_context=ground_context
        ),
        ext_lifted_task=ExtLoadedLiftedSearchContext(
            problem_path=problem_path, search_context=lifted_context
        ),
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
        source=CandidateSource.EMPTY,
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
            domain_context.base_policy_context.planning_domain,
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
            path.read_text(encoding="utf-8"),
            domain_context.base_policy_context.planning_domain,
            domain_context.classifier_context.classifier_repository,
        ),
        source=CandidateSource.FILE,
        source_file=path,
    )


def _next_result_id(domain_context: DomainContext) -> str:
    index = domain_context.next_result_index
    domain_context.next_result_index += 1
    return f"result_{index:06d}"


def _execute_details(
    failure: ExecutionFailure | None, num_rollouts: int
) -> ExecuteObservationDetails:
    if failure is None:
        return ExecuteObservationDetails(
            failure_problem_file=None,
            failure_status=None,
            num_rollouts=num_rollouts,
        )
    return ExecuteObservationDetails(
        failure_problem_file=failure.task.problem_path.name,
        failure_status=failure.result.status,
        num_rollouts=num_rollouts,
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
        state_index = state_summary(graph, int(vertex))["state_index"]
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


def rotate_smallest_state_id_first(state_ids: list[str]) -> tuple[str, ...]:
    if not state_ids:
        return ()

    def key(value: str) -> tuple[int, str]:
        suffix = value[1:] if value.startswith("s") else value
        try:
            return (int(suffix), value)
        except ValueError:
            return (0, value)

    start = min(range(len(state_ids)), key=lambda index: key(state_ids[index]))
    return tuple(state_ids[start:] + state_ids[:start])


def _witness_parts(
    *, proof: ProofResult, category: CounterexampleKind, witness: FailureWitness
) -> tuple[str, ...]:
    if category is CounterexampleKind.CYCLE and isinstance(witness, list):
        return rotate_smallest_state_id_first(
            [_state_id_for_vertex(proof, int(vertex)) for vertex in witness]
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
) -> FailureFingerprint | None:
    if status is ValidationStatus.SUCCESS:
        return None
    items = failure_items(
        proof,
        max_open_state_counterexamples=1,
        max_deadend_transition_counterexamples=1,
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
        category=proof.status.name,
    )


def _execute_fingerprint(
    *,
    kind: ValidationKind,
    status: ValidationStatus,
    failure: ExecutionFailure | None,
) -> FailureFingerprint | None:
    if failure is None or status is ValidationStatus.SUCCESS:
        return None
    return _proof_fingerprint(
        kind=kind,
        status=status,
        problem_file=failure.task.problem_path.name,
        proof=failure.result,
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
    category = state_graph_status.name if state_graph_status is not None else "misclassified_states"
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


def _classifier_details(
    counts: ClassifierProofCounts,
    *,
    state_graph_status: SearchStatus | None = None,
) -> ClassifierObservationDetails:
    return ClassifierObservationDetails(
        counts=counts,
        state_graph_status=state_graph_status,
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
    search_budget: SearchBudget = SearchBudget(max_num_states=None, max_time_seconds=None),
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ExecutePolicyResult:
    first_failure = None
    successful_results: list[tuple[int, ProofResult]] = []
    for seed in rollout_seeds(num_rollouts, random_seed, random_seed_start):
        proof = find_base_solution(
            context.base_task.search_context,
            policy.value,
            configure_search_options(
                GroundSketchSearchOptions(),
                random_seed=seed,
                shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
                max_arity=max_arity,
                max_num_states=search_budget.max_num_states,
                max_time_seconds=search_budget.max_time_seconds,
            ),
        )
        if is_success_status(proof.status) or is_goal_open_state_result(proof):
            successful_results.append((seed, proof))
        elif first_failure is None:
            first_failure = BaseExecutionFailure(task=context.base_task, result=proof)
    status = ValidationStatus.SUCCESS if first_failure is None else ValidationStatus.FAILURE
    result_id = _next_result_id(context.domain_context)
    details = _execute_details(first_failure, num_rollouts)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.BASE_EXECUTE,
        status=status,
        candidate=policy,
        classifier=classifier,
        details=details,
        fingerprint=_execute_fingerprint(
            kind=ValidationKind.BASE_EXECUTE, status=status, failure=first_failure
        ),
    )
    return ExecutePolicyResult(
        result_id,
        ValidationKind.BASE_EXECUTE,
        status,
        context,
        policy,
        observation,
        classifier,
        first_failure,
        tuple(successful_results),
        num_rollouts,
        search_budget,
        plan_trace_budget,
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
    search_budget: SearchBudget = SearchBudget(max_num_states=None, max_time_seconds=None),
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ExecuteModuleProgramResult:
    first_failure = None
    successful_results: list[tuple[int, ProofResult]] = []
    for seed in rollout_seeds(num_rollouts, random_seed, random_seed_start):
        proof = find_ext_solution(
            context.ext_task.search_context,
            module_program.value,
            configure_search_options(
                GroundModuleProgramSearchOptions(),
                random_seed=seed,
                shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
                max_arity=max_arity,
                max_num_states=search_budget.max_num_states,
                max_time_seconds=search_budget.max_time_seconds,
            ),
        )
        if is_success_status(proof.status) or is_goal_open_state_result(proof):
            successful_results.append((seed, proof))
        elif first_failure is None:
            first_failure = ExtExecutionFailure(task=context.ext_task, result=proof)
    status = ValidationStatus.SUCCESS if first_failure is None else ValidationStatus.FAILURE
    result_id = _next_result_id(context.domain_context)
    details = _execute_details(first_failure, num_rollouts)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.EXT_EXECUTE,
        status=status,
        candidate=module_program,
        classifier=classifier,
        details=details,
        fingerprint=_execute_fingerprint(
            kind=ValidationKind.EXT_EXECUTE, status=status, failure=first_failure
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
        first_failure,
        tuple(successful_results),
        num_rollouts,
        search_budget,
        plan_trace_budget,
    )


def prove_policy(
    context: TaskContext,
    policy: Policy,
    *,
    classifier: Classifier | None = None,
    search_budget: SearchBudget = SearchBudget(max_num_states=100_000, max_time_seconds=5.0),
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ProvePolicyResult:
    max_num_states, max_time_seconds = _required_budget_values(
        search_budget, name="prove_policy search_budget"
    )
    proof = prove_base_solution(
        context.base_task.search_context,
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
        classifier=classifier,
        details=_proof_details(proof),
        fingerprint=_proof_fingerprint(
            kind=ValidationKind.BASE_PROVE,
            status=status,
            problem_file=context.problem_file.name,
            proof=proof,
        ),
    )
    return ProvePolicyResult(
        result_id,
        ValidationKind.BASE_PROVE,
        status,
        context,
        policy,
        observation,
        proof,
        search_budget,
        plan_trace_budget,
    )


def prove_module_program(
    context: TaskContext,
    module_program: ModuleProgram,
    *,
    classifier: Classifier | None = None,
    search_budget: SearchBudget = SearchBudget(max_num_states=100_000, max_time_seconds=5.0),
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
    proof = prove_ext_solution(context.ext_task.search_context, module_program.value, options)
    status = ValidationStatus.SUCCESS if proof.is_successful() else ValidationStatus.FAILURE
    result_id = _next_result_id(context.domain_context)
    observation = _validation_observation(
        result_id=result_id,
        kind=ValidationKind.EXT_PROVE,
        status=status,
        candidate=module_program,
        classifier=classifier,
        details=_proof_details(proof),
        fingerprint=_proof_fingerprint(
            kind=ValidationKind.EXT_PROVE,
            status=status,
            problem_file=context.problem_file.name,
            proof=proof,
        ),
    )
    return ProveModuleProgramResult(
        result_id,
        ValidationKind.EXT_PROVE,
        status,
        context,
        module_program,
        observation,
        proof,
        search_budget,
        plan_trace_budget,
    )


def prove_classifier(
    context: TaskContext,
    classifier: Classifier,
    *,
    max_num_states: int = 1_000_000,
    max_time_seconds: float = 1_000_000_000.0,
) -> ProveClassifierResult:
    generation_options = StateGraphGenerationOptions()
    generation_options.max_num_states = max_num_states
    generation_options.max_time = max_time_seconds
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
        )

    graph = annotate_ground_state_graph(
        context.base_task.search_context, graph_result.graph, StateGraphCostMode.UNIT_COST
    ).get_forward_graph()
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    states = 0
    unsolvable = 0
    false_positive = 0
    false_negative = 0
    for vertex in graph.get_vertex_indices():
        states += 1
        label = graph.get_vertex_property(vertex)
        actually_solvable = not bool(label.is_unsolvable)
        if not actually_solvable:
            unsolvable += 1
        predicted_unsolvable = bool(
            classify(classifier.value, GroundEvaluationContext(label.state, builder, denotations))
        )
        if predicted_unsolvable and actually_solvable:
            false_positive += 1
        elif not predicted_unsolvable and not actually_solvable:
            false_negative += 1
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
        result_id, ValidationKind.UNS_PROVE, status, context, classifier, observation, counts
    )

