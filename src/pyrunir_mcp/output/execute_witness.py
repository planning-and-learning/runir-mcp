"""Convert execute-policy trace dicts (the `_trace_from_result` output) to output.policy
documents. Execute already extracts states/transitions/cycle from its result graph; this only
reserializes that dict (so it stays decoupled from the proof-graph label types) and is
unit-testable with synthetic traces.
"""

from __future__ import annotations

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import (
    Cycle,
    Successor,
    WitnessState,
    WitnessTransition,
    counterexample_document,
    resolve_flags,
    successors_document,
    trace_document,
)
from pyrunir_mcp.tables import Document


def _memory(state: JsonObject) -> tuple[str, str, str] | None:
    if "memory" not in state:
        return None
    return (str(state.get("module", "")), str(state["memory"]), str(state.get("memory_kind", "")))


def _flags(state: JsonObject, *, start: int | None, cycle_indices: set[int], witness: int | None, category: str) -> tuple[str, ...]:
    index = int(state["state_index"])
    return resolve_flags(
        initial=index == start,
        open_state=index == witness and category == "open_state",
        witness=index == witness,
        cycle=index in cycle_indices,
        deadend=index == witness and category == "deadend",
        truncated=bool(state.get("truncated")),
    )


def _state(state: JsonObject, *, flags: tuple[str, ...]) -> WitnessState:
    return WitnessState(
        state=int(state["state_index"]),
        features=state.get("feature_values", {}),
        fluent=tuple(state.get("fluent_facts", ())),
        derived=tuple(state.get("derived_atoms", ())),
        flags=flags,
        vertex=int(state["vertex_index"]) if "vertex_index" in state else None,
        memory=_memory(state),
    )


def _delta(feature_delta: JsonObject) -> dict[str, tuple]:
    return {symbol: (change["before"], change["after"]) for symbol, change in feature_delta.items()}


def _transition(transition: JsonObject, *, ext: bool) -> WitnessTransition:
    endpoint = ("source_vertex_index", "target_vertex_index") if ext else ("source_state_index", "target_state_index")
    return WitnessTransition(
        step=int(transition["step"]),
        source=int(transition[endpoint[0]]),
        target=int(transition[endpoint[1]]),
        action=transition.get("action"),
        rule=transition.get("module_rule"),
        delta=_delta(transition.get("feature_delta", {})),
    )


def documents(trace: JsonObject, dicts: Dictionaries, *, ext: bool) -> tuple[Document, Document | None]:
    """Return (counterexample, trace | None) documents for one execute trace."""
    states = [state for state in trace.get("states", []) if isinstance(state, dict)]
    transitions = [t for t in trace.get("transitions", []) if isinstance(t, dict)]
    category = str(trace.get("failure_category") or "")
    features = list(trace.get("features", []))
    header = [
        ("tool", str(trace.get("tool", "execute_policy"))),
        ("id", str(trace.get("id", ""))),
        ("category", category),
        ("status", str(trace.get("status", ""))),
        ("problem", str(trace.get("problem_file", ""))),
        ("seed", str((trace.get("options") or {}).get("random_seed", ""))),
    ]

    cycle = trace.get("cycle") if isinstance(trace.get("cycle"), dict) else None
    cycle_indices = {int(i) for i in cycle.get("cycle_state_indices", [])} if cycle else set()
    start = int(transitions[0]["source_state_index"]) if transitions else (int(states[0]["state_index"]) if states else None)
    witness = int(states[-1]["state_index"]) if states else None

    def witness_states(state_dicts):
        return [_state(state, flags=_flags(state, start=start, cycle_indices=cycle_indices, witness=witness, category=category)) for state in state_dicts]

    trace_doc = (
        trace_document(header=header, feature_symbols=features, states=witness_states(states), transitions=[_transition(t, ext=ext) for t in transitions], dicts=dicts, ext=ext)
        if states
        else None
    )

    if cycle:
        cycle_states = [state for state in states if int(state["state_index"]) in cycle_indices]
        steps = {int(step) for step in cycle.get("cycle_transition_steps", [])}
        cycle_transitions = [t for t in transitions if int(t["step"]) in steps]
        counterexample = counterexample_document(
            header=header, feature_symbols=features, states=witness_states(cycle_states),
            transitions=[_transition(t, ext=ext) for t in cycle_transitions],
            cycle=Cycle(
                state_indices=tuple(int(i) for i in cycle.get("cycle_state_indices", [])),
                vertex_indices=tuple(int(i) for i in cycle.get("cycle_vertex_indices", [])) if ext else (),
                transition_steps=tuple(int(s) for s in cycle.get("cycle_transition_steps", [])),
            ),
            dicts=dicts, ext=ext,
        )
    else:
        counterexample = counterexample_document(
            header=header, feature_symbols=features, states=witness_states(states[-1:]),
            transitions=[], cycle=None, dicts=dicts, ext=ext,
        )
    return counterexample, trace_doc


def successors(trace: JsonObject, dicts: Dictionaries, *, ext: bool) -> Document | None:
    """Build the successors document from a `successors` list the service attached to the trace."""
    rows = [row for row in trace.get("successors", []) if isinstance(row, dict)]
    if not rows:
        return None
    features = list(trace.get("features", []))
    header = [("tool", str(trace.get("tool", "execute_policy"))), ("id", str(trace.get("id", ""))), ("category", str(trace.get("failure_category") or ""))]
    built = [
        Successor(
            src=int(row["src"]),
            target=_state(row["target"], flags=resolve_flags(goal=bool(row["target"].get("is_goal")), deadend=bool(row["target"].get("is_deadend")))),
            action=row.get("action"),
            rule=row.get("module_rule"),
            delta=_delta(row.get("feature_delta", {})),
        )
        for row in rows
    ]
    return successors_document(header=header, feature_symbols=features, successors=built, dicts=dicts, ext=ext)
