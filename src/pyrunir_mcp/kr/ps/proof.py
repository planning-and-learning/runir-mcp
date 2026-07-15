from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import TypeAlias
from pyrunir.datasets import (
    StateGraphEdgeLabel,
)
from pyrunir.kr.ps.base import (
    GroundSketchProofGraph,
    GroundSketchProofResults,
    GroundSketchProofVertexLabel,
    SketchProofEdgeLabel,
    SketchProofStatus,
)
from pyrunir.kr.ps.base import (
    Rule as SketchRule,
)
from pyrunir.kr.ps.ext import (
    GroundModuleProgramProofGraph,
    GroundModuleProgramProofResults,
    GroundModuleProgramProofVertexLabel,
    ModuleProgramProofStatus,
    RuleVariant,
)
from pytyr.formalism.planning import GroundAction
from pytyr.planning.ground import State as GroundState

from pyrunir_mcp.enums import CounterexampleKind
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.keys import (
    Keys,
)
from pyrunir_mcp.kr.ps.frontier import FrontierExpander
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import (
    Successor,
    WitnessTransition,
    counterexample_document,
    successors_document,
    trace_document,
)
from pyrunir_mcp.output.proof_witness import (
    successor as build_successor,
)
from pyrunir_mcp.output.proof_witness import (
    witness_state,
    witness_transition,
)
from pyrunir_mcp.tables import Document

ProofGraph: TypeAlias = GroundSketchProofGraph | GroundModuleProgramProofGraph
ProofVertexLabel: TypeAlias = GroundSketchProofVertexLabel | GroundModuleProgramProofVertexLabel
ProofResult: TypeAlias = GroundSketchProofResults | GroundModuleProgramProofResults
ProofRule: TypeAlias = SketchRule | RuleVariant
ProofStatus: TypeAlias = SketchProofStatus | ModuleProgramProofStatus
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


def _label_is_goal(label: object) -> bool:
    if isinstance(
        label,
        GroundSketchProofVertexLabel | GroundModuleProgramProofVertexLabel,
    ):
        return bool(getattr(label, "is_goal", False))
    raise TypeError(f"unsupported proof vertex label: {type(label).__name__}")


def _state_is_goal(result: ProofResult, vertex: int) -> bool:
    graph = getattr(result, "graph", None)
    if graph is None:
        return False
    return _label_is_goal(graph.get_vertex_property(int(vertex)))


def status_name(status: ProofStatus) -> str:
    return str(status.name).lower()


def failure_items(
    result: ProofResult,
    *,
    max_counterexamples: int,
) -> list[FailureItem]:
    """Return one optional cycle plus at most ``max_counterexamples`` other failures."""
    items: list[FailureItem] = []
    if result.cycle:
        items.append((CounterexampleKind.CYCLE, [int(vertex) for vertex in result.cycle]))

    if max_counterexamples <= 0:
        return items

    counterexamples: list[FailureItem] = []
    for raw_vertex in result.deadend_states:
        vertex = int(raw_vertex)
        if not _state_is_goal(result, vertex):
            counterexamples.append((CounterexampleKind.DEADEND, vertex))
        if len(counterexamples) == max_counterexamples:
            break

    for raw_vertex in result.open_states:
        if len(counterexamples) == max_counterexamples:
            break
        vertex = int(raw_vertex)
        if _state_is_goal(result, vertex):
            continue
        counterexamples.append((CounterexampleKind.OPEN_STATE, vertex))

    items.extend(counterexamples)
    return items


def _vertex_indices(graph: ProofGraph) -> list[int]:
    return [int(vertex) for vertex in graph.get_vertex_indices()]


def _out_edge_indices(graph: ProofGraph, vertex: int) -> list[int]:
    return [int(edge) for edge in graph.get_out_edge_indices(int(vertex))]


def _label_is_initial(label: object) -> bool:
    if isinstance(
        label,
        GroundSketchProofVertexLabel | GroundModuleProgramProofVertexLabel,
    ):
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


def _cycle_edges(graph: ProofGraph, vertices: list[int]) -> list[int]:
    edges: list[int] = []
    for source, target in zip(vertices, vertices[1:] + vertices[:1]):
        for edge in _out_edge_indices(graph, source):
            if int(graph.get_target(edge)) == target:
                edges.append(edge)
                break
    return edges


def _label_state(label: object) -> GroundState:
    if isinstance(label, GroundModuleProgramProofVertexLabel):
        return label.execution_state.state
    if isinstance(label, GroundSketchProofVertexLabel):
        return label.state
    raise TypeError(f"unsupported proof vertex label: {type(label).__name__}")


def witness_ground_state(graph: ProofGraph, witness: FailureWitness) -> GroundState:
    return _label_state(graph.get_vertex_property(_witness_vertex(witness)))


def state_summary(
    graph: ProofGraph,
    vertex: int,
    evidence: StateEvidence | None = None,
) -> JsonObject:
    label = graph.get_vertex_property(int(vertex))
    state = _label_state(label)
    out: JsonObject = {
        Keys.STATE_INDEX: int(state.get_index()),
    }
    if isinstance(label, GroundModuleProgramProofVertexLabel):
        stack = label.execution_state.call_stack
        out[Keys.MEMORY] = str(stack.memory_state.get_name())
        out[Keys.MODULE] = str(stack.module.get_name())
        out[Keys.IS_INITIAL] = bool(label.is_initial)
        out[Keys.IS_GOAL] = bool(label.is_goal)
        out[Keys.IS_UNSOLVABLE] = bool(label.is_unsolvable)
    else:
        out[Keys.IS_INITIAL] = bool(label.is_initial)
        out[Keys.IS_GOAL] = bool(label.is_goal)
        out[Keys.IS_UNSOLVABLE] = bool(label.is_unsolvable)
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
    out: JsonObject = {}
    prop = graph.get_edge_property(int(edge))
    if isinstance(prop, SketchProofEdgeLabel):
        out[Keys.ACTION] = _format_ground_action(prop.transition)
        out[Keys.RULE] = _format_module_rule(prop.rule)
        return out
    state_transition = prop.state_transition
    if state_transition is not None:
        out[Keys.ACTION] = _format_ground_action(state_transition.action)
    out[Keys.RULE] = _format_module_rule(prop.rule)
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
    vertices = _vertices_for_edges(graph, path_edges)
    states = [
        witness_state(
            state_summary(graph, vertex, evidence),
            witness=vertex in witness_vertices,
        )
        for vertex in vertices
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


def successful_trace_artifacts(
    graph: ProofGraph,
    evidence: StateEvidence | None,
    *,
    max_traces: int,
    feature_symbols: list[str],
    dicts: Dictionaries,
    ext: bool,
    header: list[tuple[str, str]],
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> list[Document]:
    """Return traces to at most ``max_traces`` distinct reachable goal vertices."""
    traces: list[Document] = []
    if max_traces <= 0:
        return traces
    for vertex in _vertex_indices(graph):
        if not _label_is_goal(graph.get_vertex_property(vertex)):
            continue
        path_edges = _path_edges_to(graph, vertex)
        if path_edges is None:
            continue
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
        if trace is not None:
            traces.append(trace)
            if len(traces) == max_traces:
                break
    return traces


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
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=cycle_states,
            transitions=_transitions(graph, cycle_edges, evidence, ext=ext),
            cycle=True,
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
            cycle=False,
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
    else:  # CounterexampleKind.OPEN_STATE
        vertex = _witness_vertex(witness)
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=[
                witness_state(state_summary(graph, vertex, evidence), witness=True, open_state=True)
            ],
            transitions=[],
            cycle=False,
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
    # move also carries the module + resulting memory its rule lands in; a gap leaves
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
