from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TypeAlias, cast

from pyrunir.kr.ps.ext import (
    CallRule,
    DoRule,
    GroundModuleProgramSearchOptions as GroundPolicySearchOptions,
    LoadRule,
    Module,
    ModuleProgram as Policy,
    SketchRule,
    find_ground_solution,
)
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.ext.core.data_loader import LoadedSearchContext, load_grounded_search_context
from pyrunir_mcp.kr.ps.ext.core.features import ExecutionFailure, create_module_program_context
from pyrunir_mcp.kr.ps.ext.core.policy_evaluation import (
    execute_policy_on_tasks,
    failure_category_from_status,
    is_success_status,
)
from pyrunir_mcp.kr.ps.ext.core.policy_io import parse_module_program_description, read_module_program_description
from pyrunir_mcp.kr.ps.feature_evidence import Feature, feature_key, state_evidence
from pyrunir_mcp.kr.ps.proof import failure_items, witness_artifacts
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.writer import DEFAULT_FORMATS, write_run
from pyrunir_mcp.tables import Table

ModuleRule: TypeAlias = LoadRule | SketchRule | DoRule | CallRule


@dataclass(frozen=True)
class ExecutePolicyOptions:
    domain_file: Path
    problem_file: Path
    module_program_file: Path
    num_threads: int = 1
    random_seed: int = 0
    random_seed_start: int = 0
    num_rollouts: int = 1
    shuffle_labeled_succ_nodes: bool = True
    max_arity: int = 0
    max_num_states: int | None = None
    max_time_seconds: float | None = None
    dump_dir: Path | None = None
    dump_max_steps: int | None = None
    dump_max_states: int | None = None
    dump_max_successors: int | None = None


@dataclass(frozen=True)
class ExecutePolicyResult:
    policy: Policy
    tasks: list[LoadedSearchContext]
    failure: ExecutionFailure | None
    dump_dir: Path | None = None

    @property
    def is_successful(self) -> bool:
        return self.failure is None


def _module_program_sha256(module_program_file: Path) -> str:
    return hashlib.sha256(module_program_file.read_bytes()).hexdigest()


def _iter_module_rules(policy: Policy) -> list[tuple[Module, ModuleRule]]:
    rules: list[tuple[Module, ModuleRule]] = []
    for module in policy.get_modules():
        for transition in module.get_memory_transitions():
            for rule_variant in transition:
                rules.append((module, cast(ModuleRule, rule_variant.get_variant())))
    return rules


def _declared_features(value: Policy | Module) -> list[Feature]:
    features: list[Feature] = []
    features.extend(cast(list[Feature], value.get_concept_features()))
    features.extend(cast(list[Feature], value.get_boolean_features()))
    features.extend(cast(list[Feature], value.get_numerical_features()))
    return features


def _collect_features(policy: Policy) -> list[Feature]:
    features_by_key: dict[str, Feature] = {}
    for value in (policy, *policy.get_modules()):
        for feature in _declared_features(value):
            features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def _intern_rules(policy: Policy, dicts: Dictionaries) -> None:
    for module, rule in _iter_module_rules(policy):
        symbol = str(rule.get_symbol()).strip()
        if not symbol:
            continue
        module_name = str(module.get_name())
        source = dicts.memory(module_name, str(rule.get_source().get_name()), "")
        target = dicts.memory(module_name, str(rule.get_target().get_name()), "")
        dicts.rule(symbol, source, target)


def create_policy_search_options(options: ExecutePolicyOptions, random_seed: int | None = None) -> GroundPolicySearchOptions:
    search_options = GroundPolicySearchOptions()
    search_options.brfs_options.random_seed = options.random_seed if random_seed is None else random_seed
    search_options.brfs_options.shuffle_labeled_succ_nodes = options.shuffle_labeled_succ_nodes
    search_options.max_arity = options.max_arity
    if options.max_num_states is not None:
        search_options.brfs_options.max_num_states = options.max_num_states
    if options.max_time_seconds is not None:
        search_options.brfs_options.max_time = timedelta(seconds=options.max_time_seconds)
    return search_options


def _rollout_seeds(options: ExecutePolicyOptions) -> list[int]:
    if options.num_rollouts == 1:
        return [options.random_seed]
    return [options.random_seed_start + offset for offset in range(options.num_rollouts)]


def _result_failure(result) -> tuple[str | None, int | list[int] | None]:
    items = failure_items(result, max_open_state_counterexamples=1, max_deadend_transition_counterexamples=1)
    if items:
        category, witness = items[0]
        return category, witness
    if is_success_status(result.status):
        return None, None
    return failure_category_from_status(result.status), None


@dataclass
class _Representative:
    id: str
    category: str
    status: str
    seed: int
    problem: str
    counterexample: str | None
    trace: str | None
    successors: str | None


def _relative(name: str | None) -> str:
    return f"{name}.psv" if name else ""


def _execute_policy_with_dumps(options: ExecutePolicyOptions, policy: Policy, tasks: list[LoadedSearchContext]) -> ExecutionFailure | None:
    assert options.dump_dir is not None
    output_dir = options.dump_dir
    features = _collect_features(policy)
    feature_symbols = [feature_key(feature) for feature in features]
    evidence = state_evidence(features, include_facts=True)
    dicts = Dictionaries(ext=True)
    _intern_rules(policy, dicts)

    rollouts: list[JsonObject] = []
    task_rows: list[JsonObject] = []
    representatives: dict[tuple[str, str], tuple[int, LoadedSearchContext, object, int | list[int] | None]] = {}
    first_failure: ExecutionFailure | None = None

    for seed in _rollout_seeds(options):
        search_options = create_policy_search_options(options, seed)
        seed_failed, seed_category = False, None
        for index, task in enumerate(tasks, start=1):
            result = find_ground_solution(task.search_context, policy, search_options)
            print(f"[seed {seed}] [{index}/{len(tasks)}] {task.problem_path.name}: {result.status.name}", flush=True)
            category, witness = _result_failure(result)
            task_rows.append({"problem_file": task.problem_path.name, "status": result.status.name, "failure_category": category, "seed": seed})
            if not is_success_status(result.status):
                seed_failed, seed_category = True, category
                if first_failure is None:
                    first_failure = ExecutionFailure(task=task, result=result)
                if category is not None:
                    representatives.setdefault((task.problem_path.name, category), (seed, task, result, witness))
        rollouts.append({"seed": seed, "status": "FAILURE" if seed_failed else "SUCCESS", "failure_category": seed_category, "executed_tasks": len(tasks)})

    artifacts: dict[str, object] = {}
    reps: list[_Representative] = []
    for index, ((problem, category), (seed, task, result, witness)) in enumerate(representatives.items(), start=1):
        counterexample_id = f"{category}-{index:03d}"
        names: dict[str, str | None] = {"counterexample": None, "trace": None, "successors": None}
        if witness is not None:
            header = [
                ("tool", "execute_module_program"),
                ("id", counterexample_id),
                ("category", category),
                ("status", result.status.name),
                ("problem", problem),
                ("seed", str(seed)),
            ]
            counterexample, trace, successors = witness_artifacts(
                result.graph, category, witness, evidence, feature_symbols=feature_symbols, dicts=dicts, ext=True, header=header
            )
            names["counterexample"] = f"counterexamples/{category}/{counterexample_id}"
            artifacts[names["counterexample"]] = counterexample
            if trace is not None:
                names["trace"] = f"traces/{category}/{counterexample_id}"
                artifacts[names["trace"]] = trace
            if successors is not None:
                names["successors"] = f"successors/{category}/{counterexample_id}"
                artifacts[names["successors"]] = successors
        reps.append(_Representative(counterexample_id, category, result.status.name, seed, problem, names["counterexample"], names["trace"], names["successors"]))

    artifacts["failures"] = Table(
        name="failures",
        columns=["id", "category", "status", "seed", "problem", "source", "trace", "counterexample", "successors"],
        rows=[[r.id, r.category, r.status, r.seed, r.problem, "find_ground_solution", _relative(r.trace), _relative(r.counterexample), _relative(r.successors)] for r in reps],
    )
    artifacts["summary"] = Table(name="summary", columns=["id", "category", "status", "seed", "problem"], rows=[[r.id, r.category, r.status, r.seed, r.problem] for r in reps])

    paths = write_run(output_dir, {**dicts.tables(), **artifacts}, DEFAULT_FORMATS)

    manifest = {
        "tool": "execute_module_program",
        "domain_file": str(options.domain_file),
        "problem_file": str(options.problem_file),
        "module_program_file": str(options.module_program_file),
        "module_program_sha256": _module_program_sha256(options.module_program_file),
        "status": "SUCCESS" if first_failure is None else "FAILURE",
        "rollouts": rollouts,
        "tasks": task_rows,
        "distinct_failures": [
            {
                "id": r.id,
                "failure_category": r.category,
                "problem_file": r.problem,
                "seed": r.seed,
                "counterexample_path": paths.get(r.counterexample),
                "trace_path": paths.get(r.trace),
                "successors_path": paths.get(r.successors),
                "trace_available": r.trace is not None,
            }
            for r in reps
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return first_failure


def _execute_policy_rollouts_without_dumps(options: ExecutePolicyOptions, policy: Policy, tasks: list[LoadedSearchContext]) -> ExecutionFailure | None:
    first_failure = None
    for seed in _rollout_seeds(options):
        search_options = create_policy_search_options(options, seed)
        print(f"Rollout seed {seed}", flush=True)
        failure = execute_policy_on_tasks(policy, tasks, search_options)
        if failure is not None and first_failure is None:
            first_failure = failure
    return first_failure


def execute_policy(options: ExecutePolicyOptions) -> ExecutePolicyResult:
    execution_context = ExecutionContext(options.num_threads)
    context = create_module_program_context(options.domain_file)
    policy = parse_module_program_description(context, read_module_program_description(options.module_program_file))
    tasks = [load_grounded_search_context(options.domain_file, options.problem_file, execution_context)]
    if options.dump_dir is None:
        failure = _execute_policy_rollouts_without_dumps(options, policy, tasks)
    else:
        failure = _execute_policy_with_dumps(options, policy, tasks)
    return ExecutePolicyResult(policy=policy, tasks=tasks, failure=failure, dump_dir=options.dump_dir)
