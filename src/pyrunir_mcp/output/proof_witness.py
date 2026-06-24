"""Adapt proof-graph witness dicts (proof.state_summary / proof.edge_summary output) to the
`output.policy` witness objects, interning symbols into the run-global dictionaries.

Kept pure (dict in, objects out) so the conversion + flag logic is unit-testable without a
live proof graph; the graph traversal that produces the dicts lives in `proof.py`.
"""

from __future__ import annotations

from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.output.policy import Successor, WitnessState, WitnessTransition, resolve_flags


def _memory(state: JsonObject) -> tuple[str, str] | None:
    if "memory_state" not in state:
        return None
    return (str(state.get("module", "")), str(state["memory_state"]))


def _delta(before: JsonObject, after: JsonObject) -> dict[str, tuple[JsonValue, JsonValue]]:
    # Preserve feature order (matches the `[states]` column order); set intersection would not.
    return {key: (before[key], after[key]) for key in before if key in after and before[key] != after[key]}


def witness_state(
    state: JsonObject,
    *,
    witness: bool = False,
    open_state: bool = False,
    cycle: bool = False,
) -> WitnessState:
    flags = resolve_flags(
        initial=bool(state.get("is_initial")),
        goal=bool(state.get("is_goal")),
        deadend=bool(state.get("is_unsolvable")),
        open_state=open_state,
        witness=witness,
        cycle=cycle,
    )
    return WitnessState(
        state=int(state["state_index"]),
        features=state.get("feature_values", {}),
        fluent=tuple(state.get("fluent_facts", ())),
        derived=tuple(state.get("derived_atoms", ())),
        flags=flags,
        vertex=int(state["vertex_index"]) if "vertex_index" in state else None,
        memory=_memory(state),
    )


def witness_transition(
    edge: JsonObject,
    *,
    step: int,
    source: JsonObject,
    target: JsonObject,
    ext: bool,
) -> WitnessTransition:
    endpoint = "vertex_index" if ext else "state_index"
    return WitnessTransition(
        step=step,
        source=int(source[endpoint]),
        target=int(target[endpoint]),
        action=edge.get("action"),
        rule=edge.get("module_rule"),
        delta=_delta(source.get("feature_values", {}), target.get("feature_values", {})),
    )


def successor(
    source: JsonObject,
    edge: JsonObject,
    target: JsonObject,
) -> Successor:
    return Successor(
        src=int(source["vertex_index"] if "memory_state" in source else source["state_index"]),
        target=witness_state(target),
        action=edge.get("action"),
        rule=edge.get("module_rule"),
        delta=_delta(source.get("feature_values", {}), target.get("feature_values", {})),
    )
