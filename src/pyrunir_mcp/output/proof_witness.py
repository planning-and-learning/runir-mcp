"""Adapt proof-graph witness dicts (proof.state_summary / proof.edge_summary output) to the
`output.policy` witness objects, interning symbols into the run-global dictionaries.

Kept pure (dict in, objects out) so the conversion + flag logic is unit-testable without a
live proof graph; the graph traversal that produces the dicts lives in `proof.py`.
"""

from __future__ import annotations

from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.kr.ps.hstar import HeuristicSentinel
from pyrunir_mcp.output.policy import Successor, WitnessState, WitnessTransition, resolve_flags


def _int(value: JsonValue) -> int:
    if isinstance(value, bool | float | list | dict) or value is None:
        raise TypeError(f"expected int-like JSON scalar, got {type(value).__name__}")
    return int(value)


def _str_opt(value: JsonValue) -> str | None:
    return None if value is None else str(value)


def _json_object(value: JsonValue) -> JsonObject:
    return dict(value) if isinstance(value, dict) else {}


def _str_tuple(value: JsonValue) -> tuple[str, ...]:
    return tuple(str(item) for item in value) if isinstance(value, list) else ()


def _memory(state: JsonObject) -> tuple[str, str] | None:
    if "memory_state" not in state:
        return None
    return (str(state.get("module", "")), str(state["memory_state"]))


def _delta(before: JsonObject, after: JsonObject) -> dict[str, tuple[JsonValue, JsonValue]]:
    # Preserve feature order (matches the `[states]` column order); set intersection would not.
    return {key: (before[key], after[key]) for key in before if key in after and before[key] != after[key]}


def _is_deadend_value(value: JsonValue) -> bool:
    if isinstance(value, HeuristicSentinel):
        return value is HeuristicSentinel.DEADEND
    return value == HeuristicSentinel.DEADEND.value


def _is_deadend(state: JsonObject) -> bool:
    return bool(state.get("is_unsolvable")) or _is_deadend_value(state.get("hstar")) or _is_deadend_value(state.get("hlmcut"))


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
        deadend=_is_deadend(state),
        open_state=open_state,
        witness=witness,
        cycle=cycle,
    )
    return WitnessState(
        state=_int(state["state_index"]),
        hstar=state.get("hstar", ""),
        hlmcut=state.get("hlmcut", ""),
        features=_json_object(state.get("feature_values", {})),
        fluent=_str_tuple(state.get("fluent_facts", [])),
        derived=_str_tuple(state.get("derived_atoms", [])),
        flags=flags,
        vertex=_int(state["vertex_index"]) if "vertex_index" in state else None,
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
    return WitnessTransition(
        step=step,
        source=_int(source["state_index"]),
        target=_int(target["state_index"]),
        source_memory=_memory(source) if ext else None,
        target_memory=_memory(target) if ext else None,
        action=_str_opt(edge.get("action")),
        rule=_str_opt(edge.get("module_rule")),
        delta=_delta(_json_object(source.get("feature_values", {})), _json_object(target.get("feature_values", {}))),
    )


def successor(
    source: JsonObject,
    edge: JsonObject,
    target: JsonObject,
) -> Successor:
    return Successor(
        src=_int(source["state_index"]),
        source=witness_state(source),
        source_memory=_memory(source),
        target=witness_state(target),
        action=_str_opt(edge.get("action")),
        rule=_str_opt(edge.get("module_rule")),
        delta=_delta(_json_object(source.get("feature_values", {})), _json_object(target.get("feature_values", {}))),
    )
