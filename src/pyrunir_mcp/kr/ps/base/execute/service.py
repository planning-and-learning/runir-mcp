from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
import hashlib
import json
import re
from pathlib import Path
from typing import Literal, TypeAlias

from pyrunir.kr.ps.base import (
    GroundSketchProofGraph,
    GroundSketchProofResults,
    GroundSketchSearchOptions as GroundPolicySearchOptions,
    Sketch as Policy,
    find_ground_solution,
    prove_ground_solution,
)
from pyyggdrasil.execution import ExecutionContext
from pytyr.planning.ground import State

from pyrunir_mcp.feature_evidence import Feature, evaluate_features, feature_key
from pyrunir_mcp.json_types import JsonDictList, JsonObject
from pyrunir_mcp.proof import edge_summary
from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext, load_grounded_search_context
from pyrunir_mcp.kr.ps.base.core.features import ExecutionFailure, create_base_policy_context
from pyrunir_mcp.kr.ps.base.core.policy_evaluation import execute_policy_on_tasks, failure_category_from_status, is_success_status
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description, read_policy_description

NativeFailureItem: TypeAlias = tuple[Literal["cycle"], list[int]] | tuple[Literal["open_state", "deadend_transition"], int]

ARTIFACT_VERSION = 1


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
    max_time_seconds: float | None = None   # seconds (wall bound on the sub-search)
    dump_dir: Path | None = None
    dump_max_steps: int | None = None
    dump_max_states: int | None = None


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


def _collect_features(policy: Policy) -> list[Feature]:
    features_by_key: dict[str, Feature] = {}
    for getter_name in ("get_boolean_features", "get_numerical_features"):
        get_features = getattr(policy, getter_name, None)
        if not callable(get_features):
            continue
        for feature in get_features():
            features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def _state_facts(state: State) -> JsonObject:
    return {
        "state_index": int(state.get_index()),
        "fluent_facts": [str(fact) for fact in state.fluent_facts()],
        "derived_atoms": [str(atom) for atom in state.derived_atoms()],
    }


def _feature_values(state: State, features: list[Feature]) -> JsonObject:
    return evaluate_features(state, features)


def _feature_delta(before: JsonObject, after: JsonObject) -> dict[str, JsonObject]:
    return {
        key: {"before": before[key], "after": after[key]}
        for key in before.keys() & after.keys()
        if before[key] != after[key]
    }


def _rule_symbol(rule, index: int) -> str:
    get_symbol = getattr(rule, "get_symbol", None)
    if callable(get_symbol):
        return str(get_symbol()).strip()
    match = re.search(r"\(:symbol\s+([^\s)]+)", str(rule))
    if match is not None:
        return match.group(1)
    return f"rule_{index}"


def _graph_vertex_indices(graph: GroundSketchProofGraph) -> list[int]:
    get_vertex_indices = getattr(graph, "get_vertex_indices", None)
    if callable(get_vertex_indices):
        return [int(vertex) for vertex in get_vertex_indices()]
    return list(range(int(graph.get_num_vertices())))


def _graph_out_edge_indices(graph: GroundSketchProofGraph, vertex: int) -> list[int]:
    get_out_edge_indices = getattr(graph, "get_out_edge_indices", None)
    if callable(get_out_edge_indices):
        return [int(edge) for edge in get_out_edge_indices(int(vertex))]
    return [edge for edge in range(int(graph.get_num_edges())) if int(graph.get_source(edge)) == int(vertex)]


def _matched_rules(
    graph: GroundSketchProofGraph | None,
    source_state: State,
    target_state: State,
) -> JsonDictList:
    if graph is None:
        return []
    source_state_index = int(source_state.get_index())
    target_state_index = int(target_state.get_index())
    for vertex in _graph_vertex_indices(graph):
        if int(_state_from_vertex(graph, vertex).get_index()) != source_state_index:
            continue
        for edge in _graph_out_edge_indices(graph, vertex):
            target_vertex = int(graph.get_target(edge))
            if int(_state_from_vertex(graph, target_vertex).get_index()) != target_state_index:
                continue
            summary = edge_summary(graph, edge)
            symbol = summary.get("module_rule")
            if isinstance(symbol, str) and symbol:
                return [{"edge": edge, "symbol": symbol}]
    return []


def _state_index(state: State) -> int:
    return int(state.get_index())


def _state_from_vertex(graph: GroundSketchProofGraph, vertex: int) -> State:
    return graph.get_vertex_property(vertex).state


def _native_failure_items(result: GroundSketchProofResults) -> list[NativeFailureItem]:
    items: list[NativeFailureItem] = []
    if result.cycle:
        items.append(("cycle", [int(vertex) for vertex in result.cycle]))
    items.extend(("open_state", int(vertex)) for vertex in result.open_states)
    items.extend(("deadend_transition", int(edge)) for edge in result.deadend_transitions)
    return items


def _native_failure_vertices(graph: GroundSketchProofGraph, failure_items: list[NativeFailureItem]) -> list[int]:
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


def _native_counterexamples(failure_items: list[NativeFailureItem]) -> JsonDictList:
    return [{"failure_category": failure_category, "failure": item} for failure_category, item in failure_items]


def _native_cycle_description(result: GroundSketchProofResults, graph: GroundSketchProofGraph | None) -> JsonObject | None:
    if not result.cycle:
        return None
    cycle_vertex_indices = [int(vertex) for vertex in result.cycle]
    data: JsonObject = {"cycle_vertex_indices": cycle_vertex_indices}
    if graph is not None:
        data["cycle_state_indices"] = [int(_state_from_vertex(graph, vertex).get_index()) for vertex in cycle_vertex_indices]
    return data


def _policy_metadata(policy: Policy) -> tuple[list[str], JsonDictList]:
    features = [feature_key(feature) for feature in _collect_features(policy)]
    rules = [{"index": index, "symbol": _rule_symbol(rule, index)} for index, rule in enumerate(policy.get_rules())]
    return features, rules


def _dump_options(options: ExecutePolicyOptions) -> JsonObject:
    return {
        "num_threads": options.num_threads,
        "random_seed": options.random_seed,
        "random_seed_start": options.random_seed_start,
        "num_rollouts": options.num_rollouts,
        "shuffle_labeled_succ_nodes": options.shuffle_labeled_succ_nodes,
        "max_arity": options.max_arity,
        "max_num_states": options.max_num_states,
        "max_time_seconds": options.max_time_seconds,
        "dump_max_steps": options.dump_max_steps,
        "dump_max_states": options.dump_max_states,
    }


def _add_state(
    states: dict[int, JsonObject],
    state: State,
    features: list[Feature],
    max_states: int | None,
) -> None:
    state_index = int(state.get_index())
    if state_index in states:
        return
    if max_states is not None and len(states) >= max_states:
        states[state_index] = {"state_index": state_index, "truncated": True}
        return
    data = _state_facts(state)
    data["feature_values"] = _feature_values(state, features)
    states[state_index] = data


def _cycle_description(start_state_index: int | None, transitions: JsonDictList) -> JsonObject | None:
    if start_state_index is None:
        return None
    state_indices = [start_state_index]
    for transition in transitions:
        target = transition.get("target_state_index")
        if isinstance(target, int):
            state_indices.append(target)
    first_seen: dict[int, int] = {}
    for index, state_index in enumerate(state_indices):
        if state_index in first_seen:
            start = first_seen[state_index]
            return {
                "prefix_state_indices": state_indices[:start],
                "cycle_state_indices": state_indices[start : index + 1],
                "prefix_transition_steps": list(range(start)),
                "cycle_transition_steps": list(range(start, index)),
            }
        first_seen[state_index] = index
    return None


def _trace_from_result(
    *,
    options: ExecutePolicyOptions,
    policy: Policy,
    task: LoadedSearchContext,
    result: GroundSketchProofResults,
    task_index: int,
) -> JsonObject:
    features = _collect_features(policy)
    feature_names, rules = _policy_metadata(policy)
    states: dict[int, JsonObject] = {}
    transitions: JsonDictList = []
    start_state_index: int | None = None
    plan = getattr(result, "plan", None)

    native_counterexamples: JsonDictList = []
    graph = getattr(result, "graph", None)

    if plan is None:
        node = task.search_context.successor_generator.get_initial_node()
        start_state_index = int(node.get_state().get_index())
        failure_items = _native_failure_items(result)
        native_counterexamples = _native_counterexamples(failure_items)

        if graph is not None and failure_items:
            for vertex in _native_failure_vertices(graph, failure_items):
                _add_state(states, _state_from_vertex(graph, vertex), features, options.dump_max_states)
        elif failure_items:
            _add_state(states, node.get_state(), features, options.dump_max_states)

    else:
        node = plan.get_start_node()
        start_state_index = int(node.get_state().get_index())
        _add_state(states, node.get_state(), features, options.dump_max_states)
        for step, labeled in enumerate(plan.get_labeled_succ_nodes()):
            if options.dump_max_steps is not None and step >= options.dump_max_steps:
                break
            source_state = node.get_state()
            target_state = labeled.node.get_state()
            source_values = _feature_values(source_state, features)
            target_values = _feature_values(target_state, features)
            transition: JsonObject = {
                "step": step,
                "source_state_index": int(source_state.get_index()),
                "target_state_index": int(target_state.get_index()),
                "action": str(labeled.label).strip(),
                "matched_rules": _matched_rules(graph, source_state, target_state),
                "feature_delta": _feature_delta(source_values, target_values),
            }
            transitions.append(transition)
            node = labeled.node
            _add_state(states, target_state, features, options.dump_max_states)

    status = result.status.name
    status_failure_category = failure_category_from_status(result.status)
    native_failure_category = None
    if native_counterexamples:
        native_failure_category = str(native_counterexamples[0].get("failure_category"))
    failure_category = native_failure_category or status_failure_category
    cycle_info = _native_cycle_description(result, graph) or (_cycle_description(start_state_index, transitions) if status == "CYCLE" else None)
    return {
        "artifact_version": ARTIFACT_VERSION,
        "tool": "execute_policy",
        "domain_file": str(options.domain_file),
        "problem_file": str(task.problem_path),
        "sketch_file": str(options.sketch_file),
        "sketch_sha256": _file_sha256(options.sketch_file),
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
    }


def _write_dump_json(path: Path, data: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _failure_fingerprint(trace: JsonObject) -> str | None:
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


def _failure_representatives(traces: JsonDictList) -> dict[tuple[str, str], JsonObject]:
    representatives: dict[tuple[str, str], JsonObject] = {}
    for trace in traces:
        category = trace.get("failure_category")
        if category is None:
            continue
        problem = str(trace.get("problem_file") or trace.get("task_index") or "<unknown-task>")
        representatives.setdefault((problem, str(category)), trace)
    return representatives


def _write_summary(dump_dir: Path, traces: JsonDictList) -> None:
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
    representatives = _failure_representatives(traces)
    if representatives:
        lines.append("")
        lines.append("## First failure per task/category")
        for trace in representatives.values():
            fingerprint = trace.get("failure_fingerprint") or _failure_fingerprint(trace)
            failure_id = trace.get("id") or str(trace["failure_category"])
            trace_file = trace.get("trace_file")
            lines.append(
                f"- {failure_id}: {trace['problem_file']} seed {trace['options']['random_seed']} "
                f"trace `{trace_file}` fingerprint `{fingerprint}`"
            )
    with dump_dir.joinpath("summary.md").open("x", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _rollout_seeds(options: ExecutePolicyOptions) -> list[int]:
    if options.num_rollouts == 1:
        return [options.random_seed]
    return [options.random_seed_start + offset for offset in range(options.num_rollouts)]


def _trace_file_name(random_seed: int) -> str:
    return f"trace_seed-{random_seed}.json"


def _execute_single_rollout(
    *,
    options: ExecutePolicyOptions,
    policy: Policy,
    tasks: list[LoadedSearchContext],
    random_seed: int,
    dump_dir: Path | None,
) -> tuple[ExecutionFailure | None, JsonDictList]:
    rollout_options = replace(options, random_seed=random_seed)
    search_options = create_policy_search_options(rollout_options, random_seed)
    traces: JsonDictList = []
    failure = None
    num_tasks = len(tasks)
    for index, task in enumerate(tasks, start=1):
        result = find_ground_solution(task.search_context, policy, search_options)
        print(f"[seed {random_seed}] [{index}/{num_tasks}] {task.problem_path.name}: {result.status.name}", flush=True)
        trace_result = result
        trace_source = "find_ground_solution"
        if not is_success_status(result.status):
            trace_result = prove_ground_solution(task.search_context, policy, search_options)
            trace_source = "prove_ground_solution_after_execute_failure"
        if dump_dir is not None:
            trace = _trace_from_result(options=rollout_options, policy=policy, task=task, result=trace_result, task_index=index)
            trace["execute_status"] = result.status.name
            trace["counterexample_source"] = trace_source
            trace["failure_fingerprint"] = _failure_fingerprint(trace)
            trace_name = _trace_file_name(random_seed)
            trace["trace_file"] = trace_name
            traces.append(trace)
            _write_dump_json(dump_dir / trace_name, trace)
        if not is_success_status(result.status) and failure is None:
            failure = ExecutionFailure(task=task, result=trace_result)
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
    all_traces: JsonDictList = []
    first_failure = None
    rollouts: JsonDictList = []
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
    distinct_failures = _failure_representatives(all_traces)
    for failure_index, trace in enumerate(distinct_failures.values(), start=1):
        failure_category = str(trace["failure_category"])
        failure_id = f"{failure_category}-{failure_index:03d}"
        trace["id"] = failure_id
        _write_dump_json(dump_dir / "failures" / failure_category / f"{failure_id}.json", trace)
    manifest = {
        "artifact_version": ARTIFACT_VERSION,
        "tool": "execute_policy",
        "domain_file": str(options.domain_file),
        "problem_file": str(options.problem_file),
        "sketch_file": str(options.sketch_file),
        "sketch_sha256": _file_sha256(options.sketch_file),
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
                "fingerprint": trace.get("failure_fingerprint") or _failure_fingerprint(trace),
                "id": trace.get("id"),
                "failure_category": trace["failure_category"],
                "problem_file": trace["problem_file"],
                "seed": trace["options"]["random_seed"],
                "trace_file": trace["trace_file"],
            }
            for trace in distinct_failures.values()
        ],
        "tasks": [
            {
                "problem_file": trace["problem_file"],
                "status": trace["status"],
                "failure_category": trace["failure_category"],
                "seed": trace["options"]["random_seed"],
                "trace_file": trace["trace_file"],
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
    search_options.max_arity = options.max_arity
    # Bound the per-subgoal greedy sub-search so execution can't run forever on a huge
    # task; generous state budget so a correct policy still succeeds (execute = hard).
    if options.max_num_states is not None:
        search_options.brfs_options.max_num_states = options.max_num_states
    if options.max_time_seconds is not None:
        search_options.brfs_options.max_time = timedelta(seconds=options.max_time_seconds)
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
