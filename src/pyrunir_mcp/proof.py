from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable
from collections import deque

from pypddl.formalism import ParserOptions
from pytyr.formalism.planning import Parser
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.artifacts import write_native_counterexample_run
from pyrunir_mcp.planning import LoadedSearchContext, load_grounded_search_contexts


@dataclass(frozen=True)
class ProofRunResult:
    status: str
    num_tasks: int
    counterexamples: list[dict[str, Any]]


def task_name(task: LoadedSearchContext) -> str:
    return task.problem_path.name


def status_name(status: object) -> str:
    return getattr(status, "name", str(status))


def make_search_options(options: object, max_num_states: int, max_time_seconds: float) -> object:
    options.max_arity = getattr(options, "max_arity", 0)
    max_time = timedelta(seconds=max_time_seconds)
    options.brfs_options.max_num_states = max_num_states
    options.brfs_options.max_time = max_time
    options.iw_options.max_num_states = max_num_states
    options.iw_options.max_time = max_time
    return options


def failure_items(result: object) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    items.extend(("open_state", int(vertex)) for vertex in result.open_states)
    items.extend(("deadend_transition", int(edge)) for edge in result.deadend_transitions)
    if result.cycle:
        items.append(("cycle", [int(vertex) for vertex in result.cycle]))
    return items



def _vertex_indices(graph: object) -> list[int]:
    get_vertex_indices = getattr(graph, "get_vertex_indices", None)
    if callable(get_vertex_indices):
        return [int(vertex) for vertex in get_vertex_indices()]
    return list(range(int(graph.get_num_vertices())))


def _edge_indices(graph: object) -> list[int]:
    get_edge_indices = getattr(graph, "get_edge_indices", None)
    if callable(get_edge_indices):
        return [int(edge) for edge in get_edge_indices()]
    return list(range(int(graph.get_num_edges())))


def _out_edge_indices(graph: object, vertex: int) -> list[int]:
    get_out_edge_indices = getattr(graph, "get_out_edge_indices", None)
    if callable(get_out_edge_indices):
        return [int(edge) for edge in get_out_edge_indices(int(vertex))]
    return [edge for edge in _edge_indices(graph) if int(graph.get_source(edge)) == int(vertex)]


def _label_flag(label: object, name: str) -> bool:
    if not hasattr(label, name):
        return False
    value = getattr(label, name)
    if callable(value):
        value = value()
    return bool(value)


def _initial_vertices(graph: object) -> list[int]:
    vertices = _vertex_indices(graph)
    found: list[int] = []
    for vertex in vertices:
        try:
            label = graph.get_vertex_property(int(vertex))
        except Exception:  # noqa: BLE001
            continue
        if _label_flag(label, "is_initial"):
            found.append(int(vertex))
    return found or ([vertices[0]] if vertices else [])


def _path_edges_to(graph: object, target: int) -> list[int] | None:
    target = int(target)
    starts = _initial_vertices(graph)
    if target in starts:
        return []
    queue: deque[int] = deque(starts)
    seen = set(starts)
    predecessor: dict[int, tuple[int, int]] = {}
    while queue:
        source = queue.popleft()
        for edge in _out_edge_indices(graph, source):
            successor = int(graph.get_target(edge))
            if successor in seen:
                continue
            seen.add(successor)
            predecessor[successor] = (source, edge)
            if successor == target:
                path: list[int] = []
                cursor = target
                while cursor not in starts:
                    prev, via = predecessor[cursor]
                    path.append(via)
                    cursor = prev
                path.reverse()
                return path
            queue.append(successor)
    return None


def _states_for_edges(graph: object, path_edges: list[int], evidence: Callable[[object], dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not path_edges:
        starts = _initial_vertices(graph)
        return [state_summary(graph, starts[0], evidence)] if starts else []
    vertices = [int(graph.get_source(path_edges[0]))]
    vertices.extend(int(graph.get_target(edge)) for edge in path_edges)
    return [state_summary(graph, vertex, evidence) for vertex in vertices]


def _trace_from_path(
    *,
    task: LoadedSearchContext,
    result: object,
    category: str,
    witness: Any,
    path_edges: list[int] | None,
    evidence: Callable[[object], dict[str, Any]] | None,
    extra_edges: list[int] | None = None,
) -> dict[str, Any]:
    graph = result.graph
    edges = list(path_edges or []) + list(extra_edges or [])
    trace = {
        "task": task_name(task),
        "problem_path": task.problem_path.as_posix(),
        "category": category,
        "proof_status": status_name(result.status),
        "witness": witness,
        "trace_available": path_edges is not None,
        "path_edges": [int(edge) for edge in path_edges] if path_edges is not None else None,
            "states": _states_for_edges(graph, edges, evidence) if edges else (
            [state_summary(graph, int(witness), evidence)] if category == "open_state" else (
                [state_summary(graph, int(witness[0]), evidence)]
                if category == "cycle" and isinstance(witness, list) and witness else []
            )
        ),
        "transitions": [edge_summary(graph, edge) for edge in edges],
    }
    if category == "cycle" and isinstance(witness, list):
        trace["cycle_vertices"] = [int(vertex) for vertex in witness]
    return trace


def state_summary(
    graph: object,
    vertex: int,
    evidence: Callable[[object], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    label = graph.get_vertex_property(int(vertex))
    state = getattr(label, "state", None)
    if state is None and hasattr(label, "get_state"):
        state = label.get_state()
    out: dict[str, Any] = {"vertex": int(vertex)}
    if state is not None:
        try:
            out["state_id"] = int(state.get_index())
        except Exception:  # noqa: BLE001
            out["state"] = str(state)
        if evidence is not None:
            out.update(evidence(state))
    memory_state = getattr(label, "memory_state", None)
    if memory_state is not None:
        out["memory_state"] = str(memory_state)
    for attr in ("is_initial", "is_goal", "is_alive", "is_unsolvable", "goal_distance"):
        if hasattr(label, attr):
            value = getattr(label, attr)
            out[attr] = value() if callable(value) else value
    return out


def edge_summary(graph: object, edge: int) -> dict[str, Any]:
    out = {
        "edge": int(edge),
        "source": int(graph.get_source(int(edge))),
        "target": int(graph.get_target(int(edge))),
    }
    try:
        prop = graph.get_edge_property(int(edge))
        rule = getattr(prop, "rule", None)
        if rule is not None:
            out["rule"] = str(rule).strip()
        transition = getattr(prop, "transition", None) or getattr(prop, "state_transition", None)
        if transition is not None:
            out["transition"] = str(transition).strip()
    except Exception:  # noqa: BLE001
        pass
    return out


def counterexample_data(
    task: LoadedSearchContext,
    result: object,
    category: str,
    witness: Any,
    evidence: Callable[[object], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    graph = result.graph
    data: dict[str, Any] = {
        "task": task_name(task),
        "problem_path": task.problem_path.as_posix(),
        "category": category,
        "proof_status": status_name(result.status),
        "graph": {
            "num_vertices": int(graph.get_num_vertices()),
            "num_edges": int(graph.get_num_edges()),
        },
        "witness": witness,
    }
    if category == "open_state":
        path_edges = _path_edges_to(graph, int(witness))
        trace = _trace_from_path(
            task=task,
            result=result,
            category=category,
            witness=witness,
            path_edges=path_edges,
            evidence=evidence,
        )
        data["states"] = trace["states"]
        data["transitions"] = trace["transitions"]
        data["trace"] = trace
    elif category == "deadend_transition":
        edge = int(witness)
        source = int(graph.get_source(edge))
        path_edges = _path_edges_to(graph, source)
        trace = _trace_from_path(
            task=task,
            result=result,
            category=category,
            witness=witness,
            path_edges=path_edges,
            evidence=evidence,
            extra_edges=[edge],
        )
        data["transitions"] = trace["transitions"]
        data["states"] = trace["states"]
        data["trace"] = trace
    elif category == "cycle":
        vertices = [int(vertex) for vertex in witness]
        path_edges = _path_edges_to(graph, vertices[0]) if vertices else None
        trace = _trace_from_path(
            task=task,
            result=result,
            category=category,
            witness=vertices,
            path_edges=path_edges,
            evidence=evidence,
        )
        if vertices:
            cycle_state_ids = {state.get("vertex") for state in trace["states"] if isinstance(state, dict)}
            for vertex in vertices:
                if vertex not in cycle_state_ids:
                    trace["states"].append(state_summary(graph, vertex, evidence))
        data["states"] = trace["states"]
        data["transitions"] = trace["transitions"]
        data["trace"] = trace
    return data


def prove_tasks(
    *,
    domain_path: Path,
    train_dir: Path,
    num_threads: int,
    prove_one: Callable[[LoadedSearchContext], object],
    evidence: Callable[[object], dict[str, Any]] | None = None,
) -> ProofRunResult:
    execution_context = ExecutionContext(num_threads)
    tasks = load_grounded_search_contexts(domain_path, train_dir, execution_context)
    counterexamples: list[dict[str, Any]] = []
    for task in tasks:
        result = prove_one(task)
        if not result.is_successful():
            for category, witness in failure_items(result):
                counterexamples.append(counterexample_data(task, result, category, witness, evidence))
    return ProofRunResult(
        status="success" if not counterexamples else "failure",
        num_tasks=len(tasks),
        counterexamples=counterexamples,
    )


def write_proof_run(
    *,
    tool: str,
    output_dir: Path,
    metadata: dict[str, Any],
    result: ProofRunResult,
) -> dict[str, Any]:
    metadata = {**metadata, "num_tasks": result.num_tasks}
    return write_native_counterexample_run(
        tool=tool,
        status=result.status,
        output_dir=output_dir,
        metadata=metadata,
        counterexamples=result.counterexamples,
    )


def planning_domain(domain_path: Path) -> object:
    return Parser(domain_path, ParserOptions()).get_domain()
