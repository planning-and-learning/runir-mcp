"""Adapt proof-graph witness dicts (proof.state_summary / proof.edge_summary output) to the
`output.policy` witness objects, interning symbols into the run-global dictionaries.

Kept pure (dict in, objects out) so the conversion + flag logic is unit-testable without a
live proof graph; the graph traversal that produces the dicts lives in `proof.py`.
"""

from __future__ import annotations

from pyrunir_mcp.enums import HeuristicSentinel
from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.keys import (
    Keys,
)
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
    if Keys.MEMORY not in state:
        return None
    return (str(state.get(Keys.MODULE, "")), str(state[Keys.MEMORY]))


def _delta(before: JsonObject, after: JsonObject) -> dict[str, tuple[JsonValue, JsonValue]]:
    # Preserve feature order (matches the `[states]` column order); set intersection would not.
    return {key: (before[key], after[key]) for key in before if key in after and before[key] != after[key]}


def _is_deadend_value(value: JsonValue) -> bool:
    if isinstance(value, HeuristicSentinel):
        return value is HeuristicSentinel.DEADEND
    return value == HeuristicSentinel.DEADEND.value


def _is_deadend(state: JsonObject) -> bool:
    return bool(state.get(Keys.IS_UNSOLVABLE)) or _is_deadend_value(state.get(Keys.HSTAR)) or _is_deadend_value(state.get(Keys.HLMCUT))


def witness_state(
    state: JsonObject,
    *,
    witness: bool = False,
    open_state: bool = False,
    cycle: bool = False,
) -> WitnessState:
    flags = resolve_flags(
        initial=bool(state.get(Keys.IS_INITIAL)),
        goal=bool(state.get(Keys.IS_GOAL)),
        deadend=_is_deadend(state),
        open_state=open_state,
        witness=witness,
        cycle=cycle,
    )
    return WitnessState(
        state=_int(state[Keys.STATE_INDEX]),
        hstar=state.get(Keys.HSTAR, ""),
        hlmcut=state.get(Keys.HLMCUT, ""),
        features=_json_object(state.get(Keys.FEATURE_VALUES, {})),
        fluent=_str_tuple(state.get(Keys.FLUENT_ATOMS, [])),
        derived=_str_tuple(state.get(Keys.DERIVED_ATOMS, [])),
        flags=flags,
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
        source=_int(source[Keys.STATE_INDEX]),
        target=_int(target[Keys.STATE_INDEX]),
        source_memory=_memory(source) if ext else None,
        target_memory=_memory(target) if ext else None,
        action=_str_opt(edge.get(Keys.ACTION)),
        rule=_str_opt(edge.get(Keys.RULE)),
        delta=_delta(_json_object(source.get(Keys.FEATURE_VALUES, {})), _json_object(target.get(Keys.FEATURE_VALUES, {}))),
    )


def successor(
    source: JsonObject,
    edge: JsonObject,
    target: JsonObject,
) -> Successor:
    return Successor(
        src=_int(source[Keys.STATE_INDEX]),
        source=witness_state(source),
        source_memory=_memory(source),
        target=witness_state(target),
        action=_str_opt(edge.get(Keys.ACTION)),
        rule=_str_opt(edge.get(Keys.RULE)),
        delta=_delta(_json_object(source.get(Keys.FEATURE_VALUES, {})), _json_object(target.get(Keys.FEATURE_VALUES, {}))),
    )
