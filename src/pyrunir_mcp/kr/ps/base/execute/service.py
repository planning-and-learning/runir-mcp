from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pyrunir.kr.ps.base import (
    GroundSketchSearchOptions as GroundPolicySearchOptions,
    Sketch as Policy,
    find_ground_solution,
)
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext, load_grounded_search_context
from pyrunir_mcp.kr.ps.base.core.features import ExecutionFailure, collect_features, create_base_policy_context, intern_rules
from pyrunir_mcp.kr.ps.base.core.policy_evaluation import execute_policy_on_tasks
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description, read_policy_description
from pyrunir_mcp.kr.ps.execute import configure_search_options, rollout_seeds, run_execute
from pyrunir_mcp.kr.ps.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.frontier import make_frontier_expander
from pyrunir_mcp.output.dictionaries import Dictionaries


@dataclass(frozen=True)
class ExecutePolicyOptions:
    domain_file: Path
    problem_file: Path
    sketch_file: Path
    num_threads: int = 1
    random_seed: int = 0
    random_seed_start: int = 0
    num_rollouts: int = 1
    shuffle_labeled_succ_nodes: bool = True
    max_arity: int = 0
    # Per-subgoal sub-search budget for greedy execution. None => library default.
    max_num_states: int | None = None
    max_time_seconds: float | None = None
    dump_dir: Path | None = None


@dataclass(frozen=True)
class ExecutePolicyResult:
    policy: Policy
    tasks: list[LoadedSearchContext]
    failure: ExecutionFailure | None
    dump_dir: Path | None = None

    @property
    def is_successful(self) -> bool:
        return self.failure is None


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_policy_search_options(options: ExecutePolicyOptions, random_seed: int | None = None) -> GroundPolicySearchOptions:
    return configure_search_options(
        GroundPolicySearchOptions(),
        random_seed=options.random_seed if random_seed is None else random_seed,
        shuffle_labeled_succ_nodes=options.shuffle_labeled_succ_nodes,
        max_arity=options.max_arity,
        max_num_states=options.max_num_states,
        max_time_seconds=options.max_time_seconds,
    )


def _manifest_metadata(options: ExecutePolicyOptions) -> JsonObject:
    return {
        "domain_file": str(options.domain_file),
        "problem_file": str(options.problem_file),
        "sketch_file": str(options.sketch_file),
        "sketch_sha256": _file_sha256(options.sketch_file),
    }


def _execute_policy_with_dumps(options: ExecutePolicyOptions, policy: Policy, tasks: list[LoadedSearchContext]) -> ExecutionFailure | None:
    assert options.dump_dir is not None
    features = collect_features(policy)
    evidence = state_evidence(features, include_facts=True)
    dicts = Dictionaries(ext=False)
    intern_rules(policy, dicts)
    failing = run_execute(
        tool="execute_policy",
        ext=False,
        output_dir=options.dump_dir,
        seeds=rollout_seeds(options.num_rollouts, options.random_seed, options.random_seed_start),
        tasks=tasks,
        solve=lambda task, seed: find_ground_solution(task.search_context, policy, create_policy_search_options(options, seed)),
        feature_symbols=[feature_key(feature) for feature in features],
        evidence=evidence,
        dicts=dicts,
        manifest_metadata=_manifest_metadata(options),
        expander_factory=lambda task: make_frontier_expander(task.search_context, policy, evidence),
    )
    return ExecutionFailure(task=failing[0], result=failing[1]) if failing else None


def _execute_policy_rollouts_without_dumps(options: ExecutePolicyOptions, policy: Policy, tasks: list[LoadedSearchContext]) -> ExecutionFailure | None:
    first_failure = None
    for seed in rollout_seeds(options.num_rollouts, options.random_seed, options.random_seed_start):
        print(f"Rollout seed {seed}", flush=True)
        failure = execute_policy_on_tasks(policy, tasks, create_policy_search_options(options, seed))
        if failure is not None and first_failure is None:
            first_failure = failure
    return first_failure


def execute_policy(options: ExecutePolicyOptions) -> ExecutePolicyResult:
    execution_context = ExecutionContext(options.num_threads)
    context = create_base_policy_context(options.domain_file)
    policy = parse_policy_description(context, read_policy_description(options.sketch_file))
    tasks = [load_grounded_search_context(options.domain_file, options.problem_file, execution_context)]
    if options.dump_dir is None:
        failure = _execute_policy_rollouts_without_dumps(options, policy, tasks)
    else:
        failure = _execute_policy_with_dumps(options, policy, tasks)
    return ExecutePolicyResult(policy=policy, tasks=tasks, failure=failure, dump_dir=options.dump_dir)
