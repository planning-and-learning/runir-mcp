from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from collections.abc import Callable
from typing import Literal, TypeAlias, cast
from collections import deque

from pypddl.formalism import ParserOptions
from pyrunir.datasets import (
    GroundAnnotatedStateGraphVertexLabel,
    GroundStateGraphVertexLabel,
    LiftedAnnotatedStateGraphVertexLabel,
    LiftedStateGraphVertexLabel,
    StateGraphEdgeLabel,
)
from pyrunir.kr.ps.base import (
    GroundSketchProofGraph,
    GroundSketchProofResults,
    GroundSketchSearchOptions,
    LiftedSketchProofGraph,
    LiftedSketchProofResults,
    LiftedSketchSearchOptions,
    Rule as SketchRule,
    SketchProofEdgeLabel,
    SketchProofStatus,
)
from pyrunir.kr.ps.ext import (
    GroundModuleProgramProofGraph,
    GroundModuleProgramProofVertexLabel,
    GroundModuleProgramProofResults,
    GroundModuleProgramSearchOptions,
    LiftedModuleProgramProofGraph,
    LiftedModuleProgramProofVertexLabel,
    LiftedModuleProgramProofResults,
    LiftedModuleProgramSearchOptions,
    ModuleProgramProofEdgeLabel,
    ModuleProgramProofStatus,
    RuleVariant as ModuleRule,
)
from pytyr.formalism.planning import GroundAction, Parser, PlanningDomain
from pytyr.planning.ground import State
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.artifacts import write_native_counterexample_run
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.planning import LoadedSearchContext, load_grounded_search_context


@dataclass(frozen=True)
class ProofRunResult:
    status: str
    num_tasks: int
    counterexamples: list[JsonObject]


ProofEdgeLabel: TypeAlias = StateGraphEdgeLabel | SketchProofEdgeLabel | ModuleProgramProofEdgeLabel
ProofGraph: TypeAlias = (
    GroundSketchProofGraph
    | LiftedSketchProofGraph
    | GroundModuleProgramProofGraph
    | LiftedModuleProgramProofGraph
)
ProofVertexLabel: TypeAlias = (
    GroundAnnotatedStateGraphVertexLabel
    | LiftedAnnotatedStateGraphVertexLabel
    | GroundModuleProgramProofVertexLabel
    | LiftedModuleProgramProofVertexLabel
    | GroundStateGraphVertexLabel
    | LiftedStateGraphVertexLabel
)
ProofResult: TypeAlias = (
    GroundSketchProofResults
    | LiftedSketchProofResults
    | GroundModuleProgramProofResults
    | LiftedModuleProgramProofResults
)
ProofRule: TypeAlias = SketchRule | ModuleRule
ProofStatus: TypeAlias = SketchProofStatus | ModuleProgramProofStatus
ProofSearchOptions: TypeAlias = (
    GroundSketchSearchOptions
    | LiftedSketchSearchOptions
    | GroundModuleProgramSearchOptions
    | LiftedModuleProgramSearchOptions
)
FailureWitness: TypeAlias = int | list[int]
FailureItem: TypeAlias = tuple[Literal["cycle"], list[int]] | tuple[Literal["open_state", "deadend_transition"], int]
StateEvidence: TypeAlias = Callable[[State], JsonObject]


def task_name(task: LoadedSearchContext) -> str:
    return task.problem_path.name


def status_name(status: ProofStatus) -> str:
    return getattr(status, "name", str(status))


def make_search_options(options: ProofSearchOptions, max_num_states: int, max_time_seconds: float) -> ProofSearchOptions:
    options.max_arity = getattr(options, "max_arity", 0)
    max_time = timedelta(seconds=max_time_seconds)
    options.brfs_options.max_num_states = max_num_states
    options.brfs_options.max_time = max_time
    options.iw_options.max_num_states = max_num_states
    options.iw_options.max_time = max_time
    return options


def failure_items(result: ProofResult) -> list[FailureItem]:
    items: list[FailureItem] = []
    if result.cycle:
        items.append(("cycle", [int(vertex) for vertex in result.cycle]))
    items.extend(("open_state", int(vertex)) for vertex in result.open_states)
    items.extend(("deadend_transition", int(edge)) for edge in result.deadend_transitions)
    return items



def _vertex_indices(graph: ProofGraph) -> list[int]:
    get_vertex_indices = getattr(graph, "get_vertex_indices", None)
    if callable(get_vertex_indices):
        return [int(vertex) for vertex in get_vertex_indices()]
    return list(range(int(graph.get_num_vertices())))


def _edge_indices(graph: ProofGraph) -> list[int]:
    get_edge_indices = getattr(graph, "get_edge_indices", None)
    if callable(get_edge_indices):
        return [int(edge) for edge in get_edge_indices()]
    return list(range(int(graph.get_num_edges())))


def _out_edge_indices(graph: ProofGraph, vertex: int) -> list[int]:
    get_out_edge_indices = getattr(graph, "get_out_edge_indices", None)
    if callable(get_out_edge_indices):
        return [int(edge) for edge in get_out_edge_indices(int(vertex))]
    return [edge for edge in _edge_indices(graph) if int(graph.get_source(edge)) == int(vertex)]


def _label_flag(label: ProofVertexLabel, name: str) -> bool:
    if not hasattr(label, name):
        return False
    value = getattr(label, name)
    if callable(value):
        value = value()
    return bool(value)


def _initial_vertices(graph: ProofGraph) -> list[int]:
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


def _path_edges_to(graph: ProofGraph, target: int) -> list[int] | None:
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


def _states_for_edges(graph: ProofGraph, path_edges: list[int], evidence: StateEvidence | None) -> list[JsonObject]:
    if not path_edges:
        starts = _initial_vertices(graph)
        return [state_summary(graph, starts[0], evidence)] if starts else []
    vertices = [int(graph.get_source(path_edges[0]))]
    vertices.extend(int(graph.get_target(edge)) for edge in path_edges)
    return [state_summary(graph, vertex, evidence) for vertex in vertices]


def _trace_states(
    graph: ProofGraph,
    category: str,
    witness: FailureWitness,
    edges: list[int],
    evidence: StateEvidence | None,
) -> list[JsonObject]:
    if edges:
        return _states_for_edges(graph, edges, evidence)
    if category == "open_state":
        return [state_summary(graph, int(witness), evidence)]
    if category == "cycle" and isinstance(witness, list) and witness:
        return [state_summary(graph, int(witness[0]), evidence)]
    return []


def _trace_from_path(
    *,
    task: LoadedSearchContext,
    result: ProofResult,
    category: str,
    witness: FailureWitness,
    path_edges: list[int] | None,
    evidence: StateEvidence | None,
    extra_edges: list[int] | None = None,
) -> JsonObject:
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
        "states": _trace_states(graph, category, witness, edges, evidence),
        "transitions": [edge_summary(graph, edge) for edge in edges],
    }
    if category == "cycle" and isinstance(witness, list):
        trace["cycle_vertices"] = [int(vertex) for vertex in witness]
    return trace


def state_summary(
    graph: ProofGraph,
    vertex: int,
    evidence: StateEvidence | None = None,
) -> JsonObject:
    label = graph.get_vertex_property(int(vertex))
    state = getattr(label, "state", None)
    if state is None and hasattr(label, "get_state"):
        state = label.get_state()
    out: JsonObject = {"vertex": int(vertex)}
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


def _format_ground_action(action: GroundAction | StateGraphEdgeLabel | None) -> str | None:
    if action is None:
        return None

    ground_action = action.action if hasattr(action, "action") else cast(GroundAction, action)
    action_name = str(ground_action.get_action().get_name())
    row_text = str(ground_action.get_row()).strip()
    if row_text.startswith("(") and row_text.endswith(")"):
        row_text = row_text[1:-1].strip()
    arguments = ", ".join(row_text.split())
    return f"{action_name}({arguments})"


def _format_module_rule(rule: ProofRule | None) -> str | None:
    if rule is None:
        return None
    return str(rule.get_symbol()).strip()


def _edge_action(prop: ProofEdgeLabel) -> str | None:
    for name in ("transition", "state_transition", "action"):
        action = getattr(prop, name, None)
        if action is not None:
            return _format_ground_action(cast(GroundAction | StateGraphEdgeLabel, action))
    return None


def edge_summary(graph: ProofGraph, edge: int) -> JsonObject:
    out: JsonObject = {
        "edge": int(edge),
        "source": int(graph.get_source(int(edge))),
        "target": int(graph.get_target(int(edge))),
    }
    try:
        prop = graph.get_edge_property(int(edge))
        action = _edge_action(prop)
        if action is not None:
            out["action"] = action
        rule = getattr(prop, "rule", None)
        module_rule = _format_module_rule(cast(ProofRule | None, rule))
        if module_rule is not None:
            out["module_rule"] = module_rule
        transition = getattr(prop, "transition", None) or getattr(prop, "state_transition", None)
        if transition is not None:
            out["transition"] = str(transition).strip()
    except Exception as exc:  # noqa: BLE001
        out["label_error"] = {"type": type(exc).__name__, "message": str(exc)}
    return out


def counterexample_data(
    task: LoadedSearchContext,
    result: ProofResult,
    category: str,
    witness: FailureWitness,
    evidence: StateEvidence | None = None,
) -> JsonObject:
    graph = result.graph
    data: JsonObject = {
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
    problem_path: Path,
    num_threads: int,
    prove_one: Callable[[LoadedSearchContext], ProofResult],
    evidence: StateEvidence | None = None,
) -> ProofRunResult:
    execution_context = ExecutionContext(num_threads)
    task = load_grounded_search_context(domain_path, problem_path, execution_context)
    result = prove_one(task)
    counterexamples: list[JsonObject] = []
    if not result.is_successful():
        for category, witness in failure_items(result):
            counterexamples.append(counterexample_data(task, result, category, witness, evidence))
    return ProofRunResult(
        status="success" if not counterexamples else "failure",
        num_tasks=1,
        counterexamples=counterexamples,
    )


def write_proof_run(
    *,
    tool: str,
    output_dir: Path,
    metadata: JsonObject,
    result: ProofRunResult,
) -> JsonObject:
    metadata = {**metadata, "num_tasks": result.num_tasks}
    return write_native_counterexample_run(
        tool=tool,
        status=result.status,
        output_dir=output_dir,
        metadata=metadata,
        counterexamples=result.counterexamples,
    )


def planning_domain(domain_path: Path) -> PlanningDomain:
    return Parser(domain_path, ParserOptions()).get_domain()
