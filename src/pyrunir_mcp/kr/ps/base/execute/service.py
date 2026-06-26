from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pyrunir.kr.ps.base import (
    GroundSketchSearchOptions as PolicySearchOptions,
    Sketch as Policy,
    find_ground_solution,
)
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext
from pyrunir_mcp.kr.ps.base.core.execute_context import ExecuteContext, build_classifier, create_execute_context
from pyrunir_mcp.kr.ps.base.core.features import ExecutionFailure, collect_features, intern_rules
from pyrunir_mcp.kr.ps.base.core.policy_evaluation import execute_policy_on_tasks
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description, read_policy_description
from pyrunir_mcp.kr.ps.base.rollout import rollout_artifacts
from pyrunir_mcp.kr.ps.execute import configure_search_options, rollout_seeds, run_execute
from pyrunir_mcp.kr.ps.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HStarOptions
from pyrunir_mcp.kr.ps.frontier import make_frontier_expander
from pyrunir_mcp.output.dictionaries import Dictionaries


@dataclass(frozen=True)
class ExecutePolicyOptions:
    domain_file: Path
    problem_file: Path
    sketch_file: Path
    # Unsolvability classifier used to flag dead (unsolvable) states during the failure rollout.
    # None => the empty `(or)` classifier (classifies every state solvable).
    classifier_file: Path | None = None
    num_threads: int = 1
    random_seed: int = 0
    random_seed_start: int = 0
    num_rollouts: int = 1
    shuffle_labeled_succ_nodes: bool = True
    max_arity: int = 0
    # Per-subgoal sub-search budget for greedy execution. None => library default.
    max_num_states: int | None = None
    max_time_seconds: float | None = None
    hstar_max_num_states: int = 100_000
    hstar_max_time_seconds: float = 3.0
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


def create_policy_search_options(options: ExecutePolicyOptions, random_seed: int | None = None) -> PolicySearchOptions:
    return configure_search_options(
        PolicySearchOptions(),
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
        "classifier_file": str(options.classifier_file) if options.classifier_file else None,
        "hstar_max_num_states": options.hstar_max_num_states,
        "hstar_max_time_seconds": options.hstar_max_time_seconds,
    }


def _execute_policy_with_dumps(options: ExecutePolicyOptions, policy: Policy, context: ExecuteContext) -> ExecutionFailure | None:
    assert options.dump_dir is not None
    features = collect_features(policy)
    hstar = HStarEvaluator(context.lifted_task.search_context, HStarOptions(options.hstar_max_num_states, options.hstar_max_time_seconds))
    evidence = state_evidence(features, include_facts=True, hstar=hstar)
    dicts = Dictionaries(ext=False)
    intern_rules(policy, dicts)
    # Built once over the SAME parse/repositories as the grounding (see create_execute_context), so the
    # rollout's classify resolves against the very states it walks. Empty by default.
    classifier = build_classifier(context.classifier_repository, context.policy_context.planning_domain, options.classifier_file)
    failing = run_execute(
        tool="execute_policy",
        ext=False,
        output_dir=options.dump_dir,
        seeds=rollout_seeds(options.num_rollouts, options.random_seed, options.random_seed_start),
        tasks=[context.task],
        solve=lambda task, seed: find_ground_solution(task.search_context, policy, create_policy_search_options(options, seed)),
        feature_symbols=[feature_key(feature) for feature in features],
        evidence=evidence,
        dicts=dicts,
        manifest_metadata=_manifest_metadata(options),
        expander_factory=lambda task: make_frontier_expander(task.search_context, policy, evidence),
        rollout_fallback=lambda task, *, header, evidence, feature_symbols, dicts: rollout_artifacts(
            context.task.search_context, policy, features, classifier, evidence,
            feature_symbols=feature_symbols, dicts=dicts, header=header,
        ),
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
    # One parse → shared base/uns DL repositories + the grounded task. The policy, the classifier, and
    # the rollout all use these same repositories / state repository / successor generator (required
    # for the classifier's per-state evaluation to be memory-safe).
    context = create_execute_context(options.domain_file, options.problem_file, execution_context)
    policy = parse_policy_description(context.policy_context, read_policy_description(options.sketch_file))
    tasks = [context.task]
    if options.dump_dir is None:
        failure = _execute_policy_rollouts_without_dumps(options, policy, tasks)
    else:
        failure = _execute_policy_with_dumps(options, policy, context)
    return ExecutePolicyResult(policy=policy, tasks=tasks, failure=failure, dump_dir=options.dump_dir)
