from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from typing import Literal

from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory, GroundEvaluationContext
from pyrunir.kr.ps.base import (
    GroundSketchProofGraph,
    GroundSketchProofResults,
    GroundSketchSearchOptions as GroundPolicySearchOptions,
    Sketch as Policy,
    find_ground_solution,
)
from pyrunir.kr.ps.base.dl import GroundEvaluationContext as PolicyGroundEvaluationContext
from pytyr.planning import ExecutionContext
from pytyr.planning import SearchStatus
from pytyr.planning.ground import GoalCountHeuristic, astar_eager

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext, load_grounded_search_contexts
from pyrunir_mcp.kr.ps.base.core.features import ExecutionFailure, create_france_dl_feature_generator
from pyrunir_mcp.kr.ps.base.core.policy_evaluation import execute_policy_on_tasks, failure_category_from_status, is_success_status
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description, read_policy_description


ARTIFACT_VERSION = 1


@dataclass(frozen=True)
class ExecutePolicyOptions:
    domain_path: Path
    problem_dir: Path
    policy_file: Path
    num_threads: int = 1
    random_seed: int = 0
    random_seed_start: int = 0
    num_rollouts: int = 1
    shuffle_labeled_succ_nodes: bool = True
    # Per-subgoal sub-search budget for greedy execution. None => library default.
    max_num_states: int | None = None
    max_time: float | None = None   # seconds (wall bound on the sub-search)
    dump_dir: Path | None = None
    dump_state_mode: Literal["summary", "facts", "full"] = "summary"
    dump_max_steps: int | None = None
    dump_max_compatible_actions: int | None = None
    dump_max_states: int | None = None
    audit_compatible_successors: bool = False
    classify_compatible_successors: bool = False
    classifier: Literal["cheap", "astar"] = "astar"
    classifier_max_time: float = 1.0
    classifier_max_states: int = 10_000
    include_policy_metadata: bool = False
    replay_trace: Path | None = None


@dataclass(frozen=True)
class ExecutePolicyResult:
    policy: Policy
    tasks: list[LoadedSearchContext]
    failure: ExecutionFailure | None
    dump_dir: Path | None = None
    replay_errors: list[str] | None = None

    @property
    def is_successful(self) -> bool:
        return self.failure is None and not self.replay_errors


def _policy_sha256(policy_file: Path) -> str | None:
    if str(policy_file) == "-":
        return None
    return hashlib.sha256(policy_file.read_bytes()).hexdigest()


def _feature_key(feature: object) -> str:
    variant = feature.get_variant()
    symbol = variant.get_symbol()
    return symbol or str(feature)


def _collect_features(policy: Policy) -> list[object]:
    features_by_key: dict[str, object] = {}
    for rule in policy.get_rules():
        variants = list(rule.get_conditions()) + list(rule.get_effects())
        for variant in variants:
            concrete = variant.get_variant().get_variant()
            if hasattr(concrete, "get_feature"):
                feature = concrete.get_feature()
                features_by_key.setdefault(_feature_key(feature), feature)
    return list(features_by_key.values())


def _state_facts(state: object, mode: str) -> dict[str, object]:
    data: dict[str, object] = {"id": int(state.get_index())}
    if mode == "full":
        data["raw"] = str(state)
    if mode in {"facts", "full"}:
        data["static_atoms"] = [str(atom) for atom in state.static_atoms()]
        data["fluent_facts"] = [str(fact) for fact in state.fluent_facts()]
        data["derived_atoms"] = [str(atom) for atom in state.derived_atoms()]
    return data


def _feature_values(state: object, features: list[object]) -> dict[str, object]:
    context = GroundEvaluationContext(state, Builder(), DenotationRepositoryFactory().create())
    return {_feature_key(feature): feature.evaluate(context) for feature in features}


def _feature_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        key: {"before": before[key], "after": after[key]}
        for key in before.keys() & after.keys()
        if before[key] != after[key]
    }


def _matched_rules(
    policy: Policy,
    source_state: object,
    target_state: object,
    include_rule_text: bool,
) -> list[dict[str, object]]:
    context = PolicyGroundEvaluationContext(source_state, target_state, Builder(), DenotationRepositoryFactory().create())
    matches = []
    for index, rule in enumerate(policy.get_rules()):
        if rule.is_compatible_with(context):
            match: dict[str, object] = {"index": index}
            if include_rule_text:
                match["rule"] = str(rule).strip()
            matches.append(match)
    return matches


def _json_value(value: object) -> object:
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    return str(value)


def _has_compatible_successor(policy: Policy, successor_generator: object, node: object) -> bool:
    source_state = node.get_state()
    for labeled in successor_generator.get_labeled_successor_nodes(node):
        if _matched_rules(policy, source_state, labeled.node.get_state(), False):
            return True
    return False


def _successor_classification(
    *,
    policy: Policy,
    search_context: object | None,
    successor_generator: object,
    labeled: object,
    chosen_target_state: int | None,
    cycle_state_ids: set[int] | None,
    classifier: str,
    classifier_max_time: float,
    classifier_max_states: int,
) -> dict[str, object]:
    target_state_id = int(labeled.node.get_state().get_index())
    metadata: dict[str, object] = {
        "classifier": classifier,
        "classifier_max_time": classifier_max_time,
        "classifier_max_states": classifier_max_states,
    }
    if chosen_target_state is not None and target_state_id == chosen_target_state:
        metadata["chosen"] = True
    if cycle_state_ids is not None and target_state_id in cycle_state_ids:
        return {"label": "cycle", **metadata}

    if classifier == "astar" and search_context is not None:
        try:
            options = astar_eager.Options()
            options.start_node = labeled.node
            options.max_num_states = classifier_max_states
            options.max_time = timedelta(seconds=classifier_max_time)
            result = astar_eager.find_solution(
                search_context.task,
                search_context.successor_generator,
                GoalCountHeuristic(search_context.task),
                options,
            )
            status = result.status
            metadata["search_status"] = status.name
            if status == SearchStatus.SOLVED:
                return {"label": "succeeds", **metadata}
            if status in {SearchStatus.UNSOLVABLE, SearchStatus.EXHAUSTED, SearchStatus.FAILED}:
                return {"label": "known_deadend", **metadata}
            return {"label": "classifier_failure", **metadata}
        except Exception as error:
            return {"label": "classifier_failure", "reason": str(error), **metadata}

    try:
        if not _has_compatible_successor(policy, successor_generator, labeled.node):
            return {"label": "known_deadend", "reason": "no compatible policy successor", **metadata}
    except Exception as error:
        return {"label": "classifier_failure", "reason": str(error), **metadata}
    return {"label": "unknown", **metadata}


def _compatible_successors(
    policy: Policy,
    successor_generator: object,
    node: object,
    features: list[object],
    max_actions: int | None,
    include_rule_text: bool,
    classify: bool = False,
    classifier: str = "astar",
    chosen_target_state: int | None = None,
    cycle_state_ids: set[int] | None = None,
    search_context: object | None = None,
    classifier_max_time: float = 1.0,
    classifier_max_states: int = 10_000,
) -> list[dict[str, object]]:
    source_state = node.get_state()
    source_values = _feature_values(source_state, features)
    compatible = []
    for labeled in successor_generator.get_labeled_successor_nodes(node):
        target_state = labeled.node.get_state()
        matches = _matched_rules(policy, source_state, target_state, include_rule_text)
        if not matches:
            continue
        target_values = _feature_values(target_state, features)
        item = {
            "action": str(labeled.label).strip(),
            "target_state": int(target_state.get_index()),
            "matched_rules": matches,
            "feature_delta": _feature_delta(source_values, target_values),
        }
        if classify:
            item["classification"] = _successor_classification(
                policy=policy,
                search_context=search_context,
                successor_generator=successor_generator,
                labeled=labeled,
                chosen_target_state=chosen_target_state,
                cycle_state_ids=cycle_state_ids,
                classifier=classifier,
                classifier_max_time=classifier_max_time,
                classifier_max_states=classifier_max_states,
            )
        compatible.append(item)
        if max_actions is not None and len(compatible) >= max_actions:
            break
    return compatible


def _state_id(state: object) -> int:
    return int(state.get_index())


def _state_from_vertex(graph: GroundSketchProofGraph, vertex: int) -> object:
    return graph.get_vertex_property(vertex).state


def _native_failure_items(result: GroundSketchProofResults) -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = []
    items.extend(("open_state", int(vertex)) for vertex in result.open_states)
    items.extend(("deadend_transition", int(edge)) for edge in result.deadend_transitions)
    if result.cycle:
        items.append(("cycle", [int(vertex) for vertex in result.cycle]))
    return items


def _native_failure_vertices(graph: GroundSketchProofGraph, failure_items: list[tuple[str, object]]) -> list[int]:
    vertices: list[int] = []
    for failure_category, item in failure_items:
        if failure_category == "deadend_transition":
            vertices.append(int(graph.get_source(int(item))))
            vertices.append(int(graph.get_target(int(item))))
        elif failure_category == "cycle":
            vertices.extend(int(vertex) for vertex in item)
        else:
            vertices.append(int(item))
    return list(dict.fromkeys(vertices))


def _native_counterexamples(failure_items: list[tuple[str, object]]) -> list[dict[str, object]]:
    return [{"failure_category": failure_category, "failure": item} for failure_category, item in failure_items]


def _policy_metadata(policy: Policy, include_metadata: bool) -> tuple[list[str], list[dict[str, object]]]:
    features = [_feature_key(feature) for feature in _collect_features(policy)]
    if not include_metadata:
        return features, []
    rules = [{"index": index, "rule": str(rule).strip()} for index, rule in enumerate(policy.get_rules())]
    return features, rules


def _dump_options(options: ExecutePolicyOptions) -> dict[str, object]:
    return {
        "num_threads": options.num_threads,
        "random_seed": options.random_seed,
        "random_seed_start": options.random_seed_start,
        "num_rollouts": options.num_rollouts,
        "shuffle_labeled_succ_nodes": options.shuffle_labeled_succ_nodes,
        "dump_state_mode": options.dump_state_mode,
        "dump_max_steps": options.dump_max_steps,
        "dump_max_compatible_actions": options.dump_max_compatible_actions,
        "dump_max_states": options.dump_max_states,
        "audit_compatible_successors": options.audit_compatible_successors,
        "classify_compatible_successors": options.classify_compatible_successors,
        "classifier": options.classifier,
        "classifier_max_time": options.classifier_max_time,
        "classifier_max_states": options.classifier_max_states,
        "include_policy_metadata": options.include_policy_metadata,
        "replay_trace": None if options.replay_trace is None else str(options.replay_trace),
    }


def _add_state(
    states: dict[int, dict[str, object]],
    state: object,
    features: list[object],
    mode: str,
    max_states: int | None,
) -> None:
    state_id = int(state.get_index())
    if state_id in states:
        return
    if max_states is not None and len(states) >= max_states:
        states[state_id] = {"id": state_id, "truncated": True}
        return
    data = _state_facts(state, mode)
    data["feature_values"] = {key: _json_value(value) for key, value in _feature_values(state, features).items()}
    states[state_id] = data


def _cycle_description(start_state_id: int | None, transitions: list[dict[str, object]]) -> dict[str, object] | None:
    if start_state_id is None:
        return None
    state_ids = [start_state_id]
    for transition in transitions:
        target = transition.get("target_state")
        if isinstance(target, int):
            state_ids.append(target)
    first_seen: dict[int, int] = {}
    for index, state_id in enumerate(state_ids):
        if state_id in first_seen:
            start = first_seen[state_id]
            return {
                "prefix_state_ids": state_ids[:start],
                "cycle_state_ids": state_ids[start : index + 1],
                "prefix_transition_steps": list(range(start)),
                "cycle_transition_steps": list(range(start, index)),
            }
        first_seen[state_id] = index
    return None


def _trace_from_result(
    *,
    options: ExecutePolicyOptions,
    policy: Policy,
    task: LoadedSearchContext,
    result: GroundSketchProofResults,
    task_index: int,
) -> dict[str, object]:
    features = _collect_features(policy)
    feature_names, rules = _policy_metadata(policy, options.include_policy_metadata)
    states: dict[int, dict[str, object]] = {}
    transitions: list[dict[str, object]] = []
    start_state_id: int | None = None
    plan = getattr(result, "plan", None)

    native_counterexamples: list[dict[str, object]] = []
    graph = getattr(result, "graph", None)

    if plan is None:
        node = task.search_context.successor_generator.get_initial_node()
        start_state_id = int(node.get_state().get_index())
        failure_items = _native_failure_items(result)
        native_counterexamples = _native_counterexamples(failure_items)

        if graph is not None and failure_items:
            for vertex in _native_failure_vertices(graph, failure_items):
                _add_state(states, _state_from_vertex(graph, vertex), features, options.dump_state_mode, options.dump_max_states)
        else:
            _add_state(states, node.get_state(), features, options.dump_state_mode, options.dump_max_states)

        if options.audit_compatible_successors:
            initial_compatible_successors = _compatible_successors(
                policy,
                task.search_context.successor_generator,
                task.search_context.successor_generator.get_initial_node(),
                features,
                options.dump_max_compatible_actions,
                options.include_policy_metadata,
                options.classify_compatible_successors,
                options.classifier,
                search_context=task.search_context,
                classifier_max_time=options.classifier_max_time,
                classifier_max_states=options.classifier_max_states,
            )
        else:
            initial_compatible_successors = []
    else:
        initial_compatible_successors = []
        node = plan.get_start_node()
        start_state_id = int(node.get_state().get_index())
        _add_state(states, node.get_state(), features, options.dump_state_mode, options.dump_max_states)
        for step, labeled in enumerate(plan.get_labeled_succ_nodes()):
            if options.dump_max_steps is not None and step >= options.dump_max_steps:
                break
            source_state = node.get_state()
            target_state = labeled.node.get_state()
            source_values = _feature_values(source_state, features)
            target_values = _feature_values(target_state, features)
            transition: dict[str, object] = {
                "step": step,
                "source_state": int(source_state.get_index()),
                "target_state": int(target_state.get_index()),
                "action": str(labeled.label).strip(),
                "matched_rules": _matched_rules(policy, source_state, target_state, options.include_policy_metadata),
                "feature_delta": _feature_delta(source_values, target_values),
            }
            if options.audit_compatible_successors:
                transition["compatible_successors"] = _compatible_successors(
                    policy,
                    task.search_context.successor_generator,
                    node,
                    features,
                    options.dump_max_compatible_actions,
                    options.include_policy_metadata,
                    options.classify_compatible_successors,
                    options.classifier,
                    int(target_state.get_index()),
                    None,
                    task.search_context,
                    options.classifier_max_time,
                    options.classifier_max_states,
                )
            transitions.append(transition)
            node = labeled.node
            _add_state(states, target_state, features, options.dump_state_mode, options.dump_max_states)

    status = result.status.name
    status_failure_category = failure_category_from_status(result.status)
    native_failure_category = None
    if native_counterexamples:
        native_failure_category = str(native_counterexamples[0].get("failure_category"))
    failure_category = native_failure_category or status_failure_category
    cycle_info = _cycle_description(start_state_id, transitions) if status == "CYCLE" else None
    if cycle_info is not None and options.classify_compatible_successors:
        cycle_state_ids = set(cycle_info["cycle_state_ids"])
        for transition in transitions:
            if "compatible_successors" not in transition:
                continue
            for successor in transition["compatible_successors"]:
                target_state_id = successor.get("target_state")
                if isinstance(target_state_id, int) and target_state_id in cycle_state_ids:
                    classification = successor.setdefault("classification", {"classifier": options.classifier})
                    classification["label"] = "cycle"
    return {
        "artifact_version": ARTIFACT_VERSION,
        "tool": "execute_policy",
        "domain": str(options.domain_path),
        "problem": str(task.problem_path),
        "policy_file": str(options.policy_file),
        "policy_sha256": _policy_sha256(options.policy_file),
        "options": _dump_options(options),
        "status": status,
        "failure_category": failure_category,
        "task_index": task_index,
        "states": list(states.values()),
        "transitions": transitions,
        "chosen_actions": [transition["action"] for transition in transitions],
        "cycle": cycle_info,
        "features": feature_names,
        "rules": rules,
        "trace_available": plan is not None,
        "native_counterexamples": native_counterexamples,
        "initial_compatible_successors_are_audit_only": True,
        "initial_compatible_successors": initial_compatible_successors,
    }


def _write_dump_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _failure_fingerprint(trace: dict[str, object]) -> str | None:
    category = trace.get("failure_category")
    if category is None:
        return None
    transitions = trace.get("transitions") or []
    if transitions:
        last_transition = transitions[-1]
        action = str(last_transition.get("action", "")).split("\n", 1)[0]
        delta = json.dumps(last_transition.get("feature_delta", {}), sort_keys=True)
        return f"{category}|{action}|{delta}"
    states = trace.get("states") or []
    feature_values = states[-1].get("feature_values", {}) if states else {}
    return f"{category}|{json.dumps(feature_values, sort_keys=True)}"


def _write_summary(dump_dir: Path, traces: list[dict[str, object]]) -> None:
    counts: dict[str, int] = {}
    rollout_counts: dict[str, int] = {}
    for trace in traces:
        counts[trace["status"]] = counts.get(trace["status"], 0) + 1
        rollout_key = f"seed {trace['options']['random_seed']}: {trace['status']}"
        rollout_counts[rollout_key] = rollout_counts.get(rollout_key, 0) + 1
    lines = ["# execute_policy summary", ""]
    lines.extend(f"- {status}: {count}" for status, count in sorted(counts.items()))
    if rollout_counts:
        lines.append("")
        lines.append("## Rollouts")
        lines.extend(f"- {key}: {count} task(s)" for key, count in sorted(rollout_counts.items()))
    failures = [trace for trace in traces if trace["failure_category"] is not None]
    if failures:
        lines.append("")
        lines.append("## First distinct failures")
        seen = set()
        for trace in failures:
            fingerprint = trace.get("failure_fingerprint") or _failure_fingerprint(trace)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            lines.append(
                f"- {trace['failure_category']}: {trace['problem']} "
                f"seed {trace['options']['random_seed']} fingerprint `{fingerprint}`"
            )
    dump_dir.joinpath("summary.md").write_text("\n".join(lines) + "\n")


def _rollout_seeds(options: ExecutePolicyOptions) -> list[int]:
    if options.num_rollouts == 1:
        return [options.random_seed]
    return [options.random_seed_start + offset for offset in range(options.num_rollouts)]


def _execute_single_rollout(
    *,
    options: ExecutePolicyOptions,
    policy: Policy,
    tasks: list[LoadedSearchContext],
    random_seed: int,
    dump_dir: Path | None,
) -> tuple[ExecutionFailure | None, list[dict[str, object]]]:
    rollout_options = replace(options, random_seed=random_seed)
    search_options = create_policy_search_options(rollout_options, random_seed)
    traces = []
    failure = None
    num_tasks = len(tasks)
    for index, task in enumerate(tasks, start=1):
        result = find_ground_solution(task.search_context, policy, search_options)
        print(f"[seed {random_seed}] [{index}/{num_tasks}] {task.problem_path.name}: {result.status.name}", flush=True)
        if dump_dir is not None:
            trace = _trace_from_result(options=rollout_options, policy=policy, task=task, result=result, task_index=index)
            trace["failure_fingerprint"] = _failure_fingerprint(trace)
            traces.append(trace)
            trace_name = f"task-{index:03d}_seed-{random_seed}_trace.json"
            _write_dump_json(dump_dir / trace_name, trace)
        if not is_success_status(result.status):
            failure = ExecutionFailure(task=task, result=result)
            if dump_dir is not None and traces:
                trace = traces[-1]
                failure_name = f"{trace['failure_category']}_{index:03d}_seed-{random_seed}.json"
                failure_path = dump_dir / "failures" / failure_name
                _write_dump_json(failure_path, trace)
            break
    return failure, traces


def _execute_policy_with_dumps(
    options: ExecutePolicyOptions,
    policy: Policy,
    tasks: list[LoadedSearchContext],
) -> ExecutionFailure | None:
    assert options.dump_dir is not None
    dump_dir = options.dump_dir
    dump_dir.mkdir(parents=True, exist_ok=True)
    dump_dir.joinpath("failures").mkdir(exist_ok=True)
    all_traces = []
    first_failure = None
    rollouts = []
    for seed in _rollout_seeds(options):
        failure, traces = _execute_single_rollout(options=options, policy=policy, tasks=tasks, random_seed=seed, dump_dir=dump_dir)
        all_traces.extend(traces)
        rollout_status = "SUCCESS" if failure is None else "FAILURE"
        rollout_failure_category = None
        if failure is not None:
            rollout_failure_category = traces[-1]["failure_category"] if traces else failure.result.status.name.lower()
        rollouts.append(
            {
                "seed": seed,
                "status": rollout_status,
                "failure_category": rollout_failure_category,
                "executed_tasks": len(traces),
            }
        )
        if failure is not None and first_failure is None:
            first_failure = failure
    distinct_failures = {}
    for trace in all_traces:
        fingerprint = trace.get("failure_fingerprint")
        if fingerprint is not None:
            distinct_failures.setdefault(str(fingerprint), trace)
    manifest = {
        "artifact_version": ARTIFACT_VERSION,
        "tool": "execute_policy",
        "domain": str(options.domain_path),
        "problem": str(options.problem_dir),
        "policy_file": str(options.policy_file),
        "policy_sha256": _policy_sha256(options.policy_file),
        "options": _dump_options(options),
        "status": "SUCCESS" if first_failure is None else "FAILURE",
        "failure_category": None if first_failure is None else next(
            (trace["failure_category"] for trace in all_traces if trace["failure_category"] is not None),
            first_failure.result.status.name.lower(),
        ),
        "states": [],
        "transitions": [],
        "features": all_traces[0]["features"] if all_traces else [],
        "rules": all_traces[0]["rules"] if all_traces else [],
        "rollouts": rollouts,
        "distinct_failures": [
            {
                "fingerprint": fingerprint,
                "failure_category": trace["failure_category"],
                "problem": trace["problem"],
                "seed": trace["options"]["random_seed"],
                "trace_file": f"task-{trace['task_index']:03d}_seed-{trace['options']['random_seed']}_trace.json",
            }
            for fingerprint, trace in distinct_failures.items()
        ],
        "tasks": [
            {
                "problem": trace["problem"],
                "status": trace["status"],
                "failure_category": trace["failure_category"],
                "seed": trace["options"]["random_seed"],
                "trace_file": f"task-{trace['task_index']:03d}_seed-{trace['options']['random_seed']}_trace.json",
            }
            for trace in all_traces
        ],
    }
    _write_dump_json(dump_dir / "manifest.json", manifest)
    _write_summary(dump_dir, all_traces)
    return first_failure


def create_policy_search_options(options: ExecutePolicyOptions, random_seed: int | None = None) -> GroundPolicySearchOptions:
    search_options = GroundPolicySearchOptions()
    search_options.brfs_options.random_seed = options.random_seed if random_seed is None else random_seed
    search_options.brfs_options.shuffle_labeled_succ_nodes = options.shuffle_labeled_succ_nodes
    # Bound the per-subgoal greedy sub-search so execution can't run forever on a huge
    # task; generous state budget so a correct policy still succeeds (execute = hard).
    if options.max_num_states is not None:
        search_options.brfs_options.max_num_states = options.max_num_states
    if options.max_time is not None:
        search_options.brfs_options.max_time = timedelta(seconds=options.max_time)
    return search_options


def _execute_policy_rollouts_without_dumps(
    options: ExecutePolicyOptions,
    policy: Policy,
    tasks: list[LoadedSearchContext],
) -> ExecutionFailure | None:
    first_failure = None
    for seed in _rollout_seeds(options):
        search_options = create_policy_search_options(options, seed)
        print(f"Rollout seed {seed}", flush=True)
        failure = execute_policy_on_tasks(policy, tasks, search_options)
        if failure is not None and first_failure is None:
            first_failure = failure
    return first_failure


def _load_trace(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Replay trace must contain a JSON object: {path}")
    return data


def _trace_task(trace: dict[str, object], tasks: list[LoadedSearchContext]) -> LoadedSearchContext | None:
    problem = trace.get("problem")
    if not isinstance(problem, str):
        return None
    problem_path = Path(problem)
    for task in tasks:
        if task.problem_path == problem_path or task.problem_path.name == problem_path.name:
            return task
    return None


def _trace_projection(trace: dict[str, object]) -> dict[str, object]:
    return {
        "status": trace.get("status"),
        "failure_category": trace.get("failure_category"),
        "transitions": [
            {
                "step": transition.get("step"),
                "source_state": transition.get("source_state"),
                "target_state": transition.get("target_state"),
                "action": transition.get("action"),
                "matched_rules": transition.get("matched_rules"),
                "feature_delta": transition.get("feature_delta"),
            }
            for transition in trace.get("transitions", [])
        ],
        "state_features": {
            state.get("id"): state.get("feature_values")
            for state in trace.get("states", [])
            if isinstance(state, dict) and not state.get("truncated")
        },
    }


def _validate_replay_trace(
    options: ExecutePolicyOptions,
    policy: Policy,
    tasks: list[LoadedSearchContext],
) -> list[str]:
    assert options.replay_trace is not None
    trace = _load_trace(options.replay_trace)
    errors: list[str] = []
    if trace.get("tool") != "execute_policy":
        errors.append(f"tool mismatch: expected execute_policy, got {trace.get('tool')}")
    expected_policy_hash = _policy_sha256(options.policy_file)
    if trace.get("policy_sha256") != expected_policy_hash:
        errors.append("policy_sha256 mismatch")
    task = _trace_task(trace, tasks)
    if task is None:
        errors.append(f"problem not found in --problem_dir: {trace.get('problem')}")
        return errors

    trace_options = trace.get("options") if isinstance(trace.get("options"), dict) else {}
    replay_options = replace(
        options,
        random_seed=int(trace_options.get("random_seed", options.random_seed)),
        shuffle_labeled_succ_nodes=bool(trace_options.get("shuffle_labeled_succ_nodes", options.shuffle_labeled_succ_nodes)),
        dump_state_mode=str(trace_options.get("dump_state_mode", options.dump_state_mode)),
        dump_max_steps=len(trace.get("transitions", [])),
        dump_max_compatible_actions=trace_options.get("dump_max_compatible_actions", options.dump_max_compatible_actions),
        dump_max_states=None,
        audit_compatible_successors=False,
        classify_compatible_successors=False,
        classifier=str(trace_options.get("classifier", options.classifier)),
        classifier_max_time=float(trace_options.get("classifier_max_time", options.classifier_max_time)),
        classifier_max_states=int(trace_options.get("classifier_max_states", options.classifier_max_states)),
        include_policy_metadata=bool(trace_options.get("include_policy_metadata", options.include_policy_metadata)),
        dump_dir=None,
        num_rollouts=1,
        replay_trace=None,
    )
    search_options = create_policy_search_options(replay_options)
    result = find_ground_solution(task.search_context, policy, search_options)
    replayed = _trace_from_result(options=replay_options, policy=policy, task=task, result=result, task_index=int(trace.get("task_index", 1)))

    original_projection = _trace_projection(trace)
    replay_projection = _trace_projection(replayed)
    if original_projection["status"] != replay_projection["status"]:
        errors.append(f"status mismatch: {original_projection['status']} != {replay_projection['status']}")
    if original_projection["failure_category"] != replay_projection["failure_category"]:
        errors.append(
            f"failure_category mismatch: {original_projection['failure_category']} != {replay_projection['failure_category']}"
        )
    if original_projection["transitions"] != replay_projection["transitions"]:
        errors.append("transition/action/rule/feature-delta projection mismatch")
    original_states = original_projection["state_features"]
    replay_states = replay_projection["state_features"]
    for state_id, feature_values in original_states.items():
        if replay_states.get(state_id) != feature_values:
            errors.append(f"feature_values mismatch for state {state_id}")
    return errors


def execute_policy(options: ExecutePolicyOptions) -> ExecutePolicyResult:
    execution_context = ExecutionContext(options.num_threads)
    feature_generator = create_france_dl_feature_generator(options.domain_path)
    policy = parse_policy_description(feature_generator, read_policy_description(options.policy_file))
    tasks = load_grounded_search_contexts(options.domain_path, options.problem_dir, execution_context)
    if options.replay_trace is not None:
        replay_errors = _validate_replay_trace(options, policy, tasks)
        return ExecutePolicyResult(policy=policy, tasks=tasks, failure=None, dump_dir=options.dump_dir, replay_errors=replay_errors)
    if options.dump_dir is None:
        failure = _execute_policy_rollouts_without_dumps(options, policy, tasks)
    else:
        failure = _execute_policy_with_dumps(options, policy, tasks)
    return ExecutePolicyResult(policy=policy, tasks=tasks, failure=failure, dump_dir=options.dump_dir)
