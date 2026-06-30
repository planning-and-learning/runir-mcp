from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from enum import StrEnum
from typing import TypeAlias, overload

from pypddl.formalism import ParserOptions
from pyrunir.datasets import (
    GroundAnnotatedStateGraphVertexLabel,
    GroundStateGraphVertexLabel,
    StateGraphEdgeLabel,
)
from pyrunir.kr.ps.base import (
    GroundSketchProofGraph,
    GroundSketchProofResults,
    GroundSketchSearchOptions,
    Rule as SketchRule,
    SketchProofEdgeLabel,
    SketchProofStatus,
)
from pyrunir.kr.ps.ext import (
    GroundModuleProgramProofGraph,
    GroundModuleProgramProofResults,
    GroundModuleProgramProofVertexLabel,
    GroundModuleProgramSearchOptions,
    ModuleProgramProofEdgeLabel,
    ModuleProgramProofStatus,
    RuleVariant,
)
from pytyr.formalism.planning import GroundAction, Parser, PlanningDomain
from pytyr.planning.ground import State as GroundState

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.frontier import FrontierExpander
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import (
    Cycle,
    Successor,
    WitnessTransition,
    counterexample_document,
    successors_document,
    trace_document,
)
from pyrunir_mcp.output.proof_witness import (
    successor as build_successor,
    witness_state,
    witness_transition,
)
from pyrunir_mcp.output.writer import Artifact
from pyrunir_mcp.output.run import (
    RunItem,
    RunItemCategory,
    RunStatus,
    build_run_envelope,
    status_category,
)
from pyrunir_mcp.planning import LoadedSearchContext
from pyrunir_mcp.tables import Document


ProofGraph: TypeAlias = GroundSketchProofGraph | GroundModuleProgramProofGraph
ProofVertexLabel: TypeAlias = (
    GroundAnnotatedStateGraphVertexLabel
    | GroundStateGraphVertexLabel
    | GroundModuleProgramProofVertexLabel
)
ProofResult: TypeAlias = GroundSketchProofResults | GroundModuleProgramProofResults
ProofRule: TypeAlias = SketchRule | RuleVariant
ProofStatus: TypeAlias = SketchProofStatus | ModuleProgramProofStatus
ProofSearchOptions: TypeAlias = GroundSketchSearchOptions | GroundModuleProgramSearchOptions


class CounterexampleKind(StrEnum):
    CYCLE = "cycle"
    OPEN_STATE = "open_state"
    DEADEND = "deadend"
    DEADEND_TRANSITION = "deadend_transition"


FailureWitness: TypeAlias = int | list[int]
FailureItem: TypeAlias = tuple[CounterexampleKind, FailureWitness]
StateEvidence: TypeAlias = Callable[[GroundState], JsonObject]


def _witness_vertices(witness: FailureWitness) -> list[int]:
    if not isinstance(witness, list):
        raise TypeError(f"expected cycle witness, got {type(witness).__name__}")
    return [int(vertex) for vertex in witness]


def _witness_vertex(witness: FailureWitness) -> int:
    if isinstance(witness, list):
        raise TypeError("expected scalar witness, got cycle witness")
    return int(witness)


def _label_is_goal(label: ProofVertexLabel) -> bool:
    if isinstance(label, GroundAnnotatedStateGraphVertexLabel | GroundStateGraphVertexLabel):
        return bool(getattr(label, "is_goal", False))
    raise TypeError(f"unsupported proof vertex label: {type(label).__name__}")


def _open_state_is_goal(result: ProofResult, vertex: int) -> bool:
    graph = getattr(result, "graph", None)
    if graph is None:
        return False
    return _label_is_goal(graph.get_vertex_property(int(vertex)))


def is_goal_open_state_result(result: ProofResult) -> bool:
    """True when a failed search reports only open vertices that are already goal states."""
    if result.cycle or result.deadend_transitions or not result.open_states:
        return False
    return all(_open_state_is_goal(result, int(vertex)) for vertex in result.open_states)


def _open_state_is_deadend(
    result: ProofResult, vertex: int, evidence: StateEvidence | None
) -> bool:
    if evidence is None:
        return False
    graph = getattr(result, "graph", None)
    if graph is None:
        return False
    return bool(state_summary(graph, int(vertex), evidence).get("is_unsolvable"))


def task_name(task: LoadedSearchContext) -> str:
    return task.problem_path.name


def status_name(status: ProofStatus) -> str:
    return str(status.name)


@overload
def make_search_options(
    options: GroundSketchSearchOptions, max_num_states: int, max_time_seconds: float
) -> GroundSketchSearchOptions: ...


@overload
def make_search_options(
    options: GroundModuleProgramSearchOptions, max_num_states: int, max_time_seconds: float
) -> GroundModuleProgramSearchOptions: ...


def make_search_options(
    options: ProofSearchOptions, max_num_states: int, max_time_seconds: float
) -> ProofSearchOptions:
    options.max_arity = 0
    max_time = timedelta(seconds=max_time_seconds)
    options.brfs_options.max_num_states = max_num_states
    options.brfs_options.max_time = max_time
    options.iw_options.max_num_states = max_num_states
    options.iw_options.max_time = max_time
    return options


def failure_items(
    result: ProofResult,
    *,
    max_open_state_counterexamples: int,
    max_deadend_transition_counterexamples: int,
    evidence: StateEvidence | None = None,
) -> list[FailureItem]:
    items: list[FailureItem] = []
    if result.cycle:
        items.append((CounterexampleKind.CYCLE, [int(vertex) for vertex in result.cycle]))

    open_vertices = [
        int(vertex) for vertex in result.open_states if not _open_state_is_goal(result, int(vertex))
    ]
    classifier_deadends = [
        vertex for vertex in open_vertices if _open_state_is_deadend(result, vertex, evidence)
    ]
    ordinary_open = [vertex for vertex in open_vertices if vertex not in set(classifier_deadends)]

    if max_deadend_transition_counterexamples > 0:
        items.extend(
            (CounterexampleKind.DEADEND, vertex)
            for vertex in classifier_deadends[:max_deadend_transition_counterexamples]
        )
    if max_open_state_counterexamples > 0:
        items.extend(
            (CounterexampleKind.OPEN_STATE, vertex)
            for vertex in ordinary_open[:max_open_state_counterexamples]
        )
    if max_deadend_transition_counterexamples > 0:
        items.extend(
            (CounterexampleKind.DEADEND_TRANSITION, int(edge))
            for edge in result.deadend_transitions[:max_deadend_transition_counterexamples]
        )
    return items


def _vertex_indices(graph: ProofGraph) -> list[int]:
    return [int(vertex) for vertex in graph.get_vertex_indices()]


def _out_edge_indices(graph: ProofGraph, vertex: int) -> list[int]:
    return [int(edge) for edge in graph.get_out_edge_indices(int(vertex))]


def _label_is_initial(label: ProofVertexLabel) -> bool:
    if isinstance(label, GroundAnnotatedStateGraphVertexLabel | GroundStateGraphVertexLabel):
        return bool(getattr(label, "is_initial", False))
    raise TypeError(f"unsupported proof vertex label: {type(label).__name__}")


def _initial_vertices(graph: ProofGraph) -> list[int]:
    vertices = _vertex_indices(graph)
    found = [
        vertex for vertex in vertices if _label_is_initial(graph.get_vertex_property(int(vertex)))
    ]
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


def _vertices_for_edges(graph: ProofGraph, path_edges: list[int] | None) -> list[int]:
    """Vertices along a path (source of the first edge, then each target). An empty/None path
    means the witness is an initial vertex -> just that vertex."""
    if not path_edges:
        starts = _initial_vertices(graph)
        return [starts[0]] if starts else []
    vertices = [int(graph.get_source(path_edges[0]))]
    vertices.extend(int(graph.get_target(edge)) for edge in path_edges)
    return vertices


def _states_for_edges(
    graph: ProofGraph, path_edges: list[int], evidence: StateEvidence | None
) -> list[JsonObject]:
    return [
        state_summary(graph, vertex, evidence) for vertex in _vertices_for_edges(graph, path_edges)
    ]


def _cycle_edges(graph: ProofGraph, vertices: list[int]) -> list[int]:
    edges: list[int] = []
    for source, target in zip(vertices, vertices[1:] + vertices[:1]):
        for edge in _out_edge_indices(graph, source):
            if int(graph.get_target(edge)) == target:
                edges.append(edge)
                break
    return edges


def _label_state(label: ProofVertexLabel) -> GroundState:
    if isinstance(label, GroundAnnotatedStateGraphVertexLabel | GroundStateGraphVertexLabel):
        return label.state
    raise TypeError(f"unsupported proof vertex label: {type(label).__name__}")


def state_summary(
    graph: ProofGraph,
    vertex: int,
    evidence: StateEvidence | None = None,
) -> JsonObject:
    label = graph.get_vertex_property(int(vertex))
    state = _label_state(label)
    out: JsonObject = {
        "vertex_index": int(vertex),
        "state_index": int(state.get_index()),
    }
    if isinstance(label, GroundModuleProgramProofVertexLabel):
        memory = label.memory_state
        memory_view = memory.value if hasattr(memory, "value") else memory
        out["memory_state"] = str(getattr(memory_view, "get_name")())
        out["module"] = str(label.module.get_name())
    if isinstance(label, GroundAnnotatedStateGraphVertexLabel):
        out["is_initial"] = bool(getattr(label, "is_initial", False))
        out["is_goal"] = bool(getattr(label, "is_goal", False))
        out["is_alive"] = bool(label.is_alive)
        out["is_unsolvable"] = bool(label.is_unsolvable)
        out["goal_distance"] = label.goal_distance
    elif isinstance(label, GroundStateGraphVertexLabel):
        out["is_initial"] = bool(getattr(label, "is_initial", False))
        out["is_goal"] = bool(getattr(label, "is_goal", False))
    if evidence is not None:
        out.update(evidence(state))
    return out


def _format_ground_action(action: GroundAction | StateGraphEdgeLabel | None) -> str | None:
    if action is None:
        return None

    ground_action = (
        action.action if isinstance(action, StateGraphEdgeLabel) else action
    )
    action_name = str(ground_action.get_action().get_name())
    arguments = ", ".join(str(obj) for obj in ground_action.get_objects())
    return f"{action_name}({arguments})"


def _format_module_rule(rule: ProofRule | None) -> str | None:
    if rule is None:
        return None
    return str(rule.get_symbol()).strip()


def edge_summary(graph: ProofGraph, edge: int) -> JsonObject:
    out: JsonObject = {
        "edge": int(edge),
        "source_vertex_index": int(graph.get_source(int(edge))),
        "target_vertex_index": int(graph.get_target(int(edge))),
    }
    prop = graph.get_edge_property(int(edge))
    if isinstance(prop, SketchProofEdgeLabel):
        out["action"] = _format_ground_action(prop.transition)
        out["module_rule"] = _format_module_rule(prop.rule)
        out["transition"] = str(prop.transition).strip()
    elif isinstance(prop, ModuleProgramProofEdgeLabel):
        if prop.state_transition is not None:
            out["action"] = _format_ground_action(prop.state_transition)
            out["transition"] = str(prop.state_transition).strip()
        out["module_rule"] = _format_module_rule(prop.rule)
    else:
        raise TypeError(f"unsupported proof edge label: {type(prop).__name__}")
    return out


def _transitions(
    graph: ProofGraph, edges: list[int], evidence: StateEvidence | None, *, ext: bool
) -> list[WitnessTransition]:
    transitions: list[WitnessTransition] = []
    for step, edge in enumerate(edges):
        source = state_summary(graph, int(graph.get_source(edge)), evidence)
        target = state_summary(graph, int(graph.get_target(edge)), evidence)
        transitions.append(
            witness_transition(
                edge_summary(graph, edge), step=step, source=source, target=target, ext=ext
            )
        )
    return transitions


def _successors(
    graph: ProofGraph, vertices: list[int], evidence: StateEvidence | None, *, exclude: set[int]
) -> list[Successor]:
    successors: list[Successor] = []
    for vertex in vertices:
        source = state_summary(graph, vertex, evidence)
        for edge in _out_edge_indices(graph, vertex):
            target_vertex = int(graph.get_target(edge))
            if target_vertex in exclude:
                continue
            target = state_summary(graph, target_vertex, evidence)
            successors.append(build_successor(source, edge_summary(graph, edge), target))
    return successors


def _trace_document(
    graph: ProofGraph,
    path_edges: list[int] | None,
    evidence: StateEvidence | None,
    *,
    feature_symbols: list[str],
    dicts: Dictionaries,
    ext: bool,
    header: list[tuple[str, str]],
    witness_vertices: set[int],
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> Document | None:
    # `path_edges == []` means the witness IS an initial vertex: emit a singleton trace (one
    # state, no transitions). Only `None` (no path / not applicable) suppresses the trace.
    if path_edges is None:
        return None
    states = [
        witness_state(state, witness=state.get("vertex_index") in witness_vertices)
        for state in _states_for_edges(graph, path_edges, evidence)
    ]
    return trace_document(
        header=header,
        feature_symbols=feature_symbols,
        states=states,
        transitions=_transitions(graph, path_edges, evidence, ext=ext),
        dicts=dicts,
        ext=ext,
        include_hstar=include_hstar,
        include_hlmcut=include_hlmcut,
    )


def _expand_frontier(
    graph: ProofGraph,
    expander: FrontierExpander | None,
    evidence: StateEvidence | None,
    *,
    trace_vertices: list[int],
    graph_vertices: list[int],
    exclude: set[int],
) -> list[Successor]:
    """The 1-step frontier of the witness. With an `expander` (base sketch / ext module program)
    it expands every state on the trace via the successor generator + policy compatibility;
    without one it falls back to the graph's compatible out-edges of the witness vertices. The
    expander receives the graph and the deduped trace vertices so it can read each vertex's
    state (and, for ext, memory state + registers)."""
    if expander is None:
        return _successors(graph, graph_vertices, evidence, exclude=exclude)
    seen: set[int] = set()
    vertices: list[int] = []
    for vertex in trace_vertices:
        if int(vertex) not in seen:
            seen.add(int(vertex))
            vertices.append(int(vertex))
    return expander(graph, vertices)


def successful_trace_artifact(
    graph: ProofGraph,
    evidence: StateEvidence | None,
    *,
    feature_symbols: list[str],
    dicts: Dictionaries,
    ext: bool,
    header: list[tuple[str, str]],
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> Document | None:
    """Return a trace to the first reachable goal vertex in a successful proof graph."""
    for vertex in _vertex_indices(graph):
        if not _label_is_goal(graph.get_vertex_property(vertex)):
            continue
        path_edges = _path_edges_to(graph, vertex)
        if path_edges is None:
            continue
        return _trace_document(
            graph,
            path_edges,
            evidence,
            feature_symbols=feature_symbols,
            dicts=dicts,
            ext=ext,
            header=header,
            witness_vertices=set(),
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
    return None


def witness_artifacts(
    graph: ProofGraph,
    kind: CounterexampleKind,
    witness: FailureWitness,
    evidence: StateEvidence | None,
    *,
    feature_symbols: list[str],
    dicts: Dictionaries,
    ext: bool,
    header: list[tuple[str, str]],
    expander: FrontierExpander | None = None,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> tuple[Document, Document | None, Document | None]:
    """Return (counterexample, trace | None, successors | None) documents for one witness."""
    if kind == CounterexampleKind.CYCLE:
        vertices = _witness_vertices(witness)
        cycle_states = [
            witness_state(state_summary(graph, vertex, evidence), cycle=True) for vertex in vertices
        ]
        cycle_edges = _cycle_edges(graph, vertices)
        cycle = Cycle(
            state_indices=tuple(state.state for state in cycle_states),
            vertex_indices=tuple(vertices) if ext else (),
            transition_steps=tuple(range(len(cycle_edges))),
        )
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=cycle_states,
            transitions=_transitions(graph, cycle_edges, evidence, ext=ext),
            cycle=cycle,
            dicts=dicts,
            ext=ext,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        path_edges = _path_edges_to(graph, vertices[0]) if vertices else None
        trace = _trace_document(
            graph,
            path_edges,
            evidence,
            feature_symbols=feature_symbols,
            dicts=dicts,
            ext=ext,
            header=header,
            witness_vertices=set(),
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        successors = _expand_frontier(
            graph,
            expander,
            evidence,
            trace_vertices=_vertices_for_edges(graph, path_edges) + vertices,
            graph_vertices=vertices,
            exclude=set(vertices),
        )
    elif kind == CounterexampleKind.DEADEND:
        vertex = _witness_vertex(witness)
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=[witness_state(state_summary(graph, vertex, evidence), witness=True)],
            transitions=[],
            cycle=None,
            dicts=dicts,
            ext=ext,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        path_edges = _path_edges_to(graph, vertex)
        trace = _trace_document(
            graph,
            path_edges,
            evidence,
            feature_symbols=feature_symbols,
            dicts=dicts,
            ext=ext,
            header=header,
            witness_vertices={vertex},
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        successors = []
    elif kind == CounterexampleKind.DEADEND_TRANSITION:
        edge = _witness_vertex(witness)
        source_vertex, dead_vertex = int(graph.get_source(edge)), int(graph.get_target(edge))
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=[witness_state(state_summary(graph, dead_vertex, evidence), witness=True)],
            transitions=[],
            cycle=None,
            dicts=dicts,
            ext=ext,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        path_edges = _path_edges_to(graph, source_vertex)
        trace_edges = ([*path_edges, edge]) if path_edges is not None else None
        trace = _trace_document(
            graph,
            trace_edges,
            evidence,
            feature_symbols=feature_symbols,
            dicts=dicts,
            ext=ext,
            header=header,
            witness_vertices={dead_vertex},
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        successors = _expand_frontier(
            graph,
            expander,
            evidence,
            trace_vertices=_vertices_for_edges(graph, trace_edges)
            if trace_edges is not None
            else [source_vertex, dead_vertex],
            graph_vertices=[source_vertex],
            exclude=set(),
        )
    else:  # CounterexampleKind.OPEN_STATE
        vertex = _witness_vertex(witness)
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=[
                witness_state(state_summary(graph, vertex, evidence), witness=True, open_state=True)
            ],
            transitions=[],
            cycle=None,
            dicts=dicts,
            ext=ext,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        path_edges = _path_edges_to(graph, vertex)
        trace = _trace_document(
            graph,
            path_edges,
            evidence,
            feature_symbols=feature_symbols,
            dicts=dicts,
            ext=ext,
            header=header,
            witness_vertices={vertex},
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        successors = _expand_frontier(
            graph,
            expander,
            evidence,
            trace_vertices=_vertices_for_edges(graph, path_edges),
            graph_vertices=[vertex],
            exclude=set(),
        )

    # Successors are generator-expanded 1-step planning moves; they are off-graph (no proof
    # vertex), so their `tgt` is the planning state index. For module programs (ext) each taken
    # move also carries the module + resulting memory (`mod`/`mem`) its rule lands in; a gap leaves
    # them blank.
    successor_doc = (
        successors_document(
            header=header,
            feature_symbols=feature_symbols,
            successors=successors,
            dicts=dicts,
            ext=ext,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        if successors
        else None
    )
    return counterexample, trace, successor_doc


def build_proof_run(
    *,
    tool: str,
    output_dir: Path,
    metadata: JsonObject,
    task: LoadedSearchContext,
    result: ProofResult,
    feature_symbols: list[str],
    dicts: Dictionaries,
    ext: bool,
    evidence: StateEvidence | None = None,
    expander: FrontierExpander | None = None,
    max_open_state_counterexamples: int = 1,
    max_deadend_transition_counterexamples: int = 1,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> JsonObject:
    graph = result.graph
    effective_success = result.is_successful() or is_goal_open_state_result(result)
    status = RunStatus.SUCCESS if effective_success else RunStatus.FAILURE
    artifacts: dict[str, Artifact] = {}
    items: list[RunItem] = []
    if not effective_success:
        counts: dict[str, int] = {}
        for kind, witness in failure_items(
            result,
            max_open_state_counterexamples=max_open_state_counterexamples,
            max_deadend_transition_counterexamples=max_deadend_transition_counterexamples,
            evidence=evidence,
        ):
            category = RunItemCategory(kind.value)
            category_value = category.value
            counts[category_value] = counts.get(category_value, 0) + 1
            failure_id = f"{category_value}-{counts[category_value]:03d}"
            header = [
                ("tool", tool),
                ("id", failure_id),
                ("category", category_value),
                ("status", status_name(result.status)),
                ("problem", task_name(task)),
            ]
            witness_doc, trace, successors = witness_artifacts(
                graph,
                kind,
                witness,
                evidence,
                feature_symbols=feature_symbols,
                dicts=dicts,
                ext=ext,
                header=header,
                expander=expander,
                include_hstar=include_hstar,
                include_hlmcut=include_hlmcut,
            )
            names = {"witness": f"failures/{failure_id}/witness"}
            artifacts[names["witness"]] = witness_doc
            if trace is not None:
                names["trace"] = f"failures/{failure_id}/trace"
                artifacts[names["trace"]] = trace
            if successors is not None:
                names["successors"] = f"failures/{failure_id}/successors"
                artifacts[names["successors"]] = successors
            items.append(
                RunItem(
                    id=failure_id,
                    category=category,
                    task=task_name(task),
                    witness=names["witness"],
                    trace=names.get("trace"),
                    successors=names.get("successors"),
                )
            )
    return build_run_envelope(
        tool=tool,
        status=status,
        category=status_category(status_name(result.status)),
        output_dir=output_dir,
        metadata=metadata,
        dictionary_tables=dicts.tables(),
        artifacts=artifacts,
        items=items,
    )


def planning_domain(domain_path: Path) -> PlanningDomain:
    return Parser(domain_path, ParserOptions()).get_domain()
