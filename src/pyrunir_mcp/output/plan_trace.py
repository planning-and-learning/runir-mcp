"""Build open-state FF plan trace documents.

A plan trace is planner evidence from an open planning state. It is not policy/module-program
execution, so the transition section is named `[plan]` and carries only task-level state/action
information.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.tables import Document, Table


def _json_dict() -> dict[str, JsonValue]:
    return {}


def _delta_dict() -> dict[str, tuple[JsonValue, JsonValue]]:
    return {}


@dataclass(frozen=True)
class PlanTraceState:
    state: int
    features: dict[str, JsonValue] = field(default_factory=_json_dict)
    flags: tuple[str, ...] = ()
    hstar: JsonValue = ""
    hlmcut: JsonValue = ""


@dataclass(frozen=True)
class PlanStep:
    step: int
    source: int
    action: str
    target: int
    delta: dict[str, tuple[JsonValue, JsonValue]] = field(default_factory=_delta_dict)


def _state_id(index: int) -> str:
    return f"s{index}"


def _scalar(value: JsonValue) -> str:
    return "T" if value is True else "F" if value is False else str(value)


def _flags(flags: tuple[str, ...]) -> str:
    return ",".join(flags)


def _delta(delta: dict[str, tuple[JsonValue, JsonValue]], dicts: Dictionaries) -> str:
    return " ".join(
        f"{dicts.feature(s)}:{_scalar(before)}>{_scalar(after)}"
        for s, (before, after) in delta.items()
    )


def _intern_features(features: list[str], dicts: Dictionaries) -> None:
    for symbol in features:
        dicts.feature(symbol)


def _states_table(states: list[PlanTraceState], dicts: Dictionaries) -> Table:
    features = dicts.feature_symbols()
    aliases = [f"f{index}" for index in range(len(features))]
    rows: list[list[JsonValue]] = [
        [
            _state_id(state.state),
            _flags(state.flags),
            state.hstar,
            state.hlmcut,
            *[state.features.get(symbol) for symbol in features],
        ]
        for state in states
    ]
    return Table(
        name="states",
        columns=["state", "flags", "hstar", "hlmcut", *aliases],
        rows=rows,
    )


def _plan_table(steps: list[PlanStep], dicts: Dictionaries) -> Table:
    rows: list[list[JsonValue]] = [
        [
            step.step,
            _state_id(step.source),
            dicts.action(step.action),
            _state_id(step.target),
            _delta(step.delta, dicts),
        ]
        for step in steps
    ]
    return Table(
        name="plan",
        columns=["step", "source", "action", "target", "delta"],
        rows=rows,
    )


def plan_trace_document(
    *,
    header: list[tuple[str, str]],
    feature_symbols: list[str],
    states: list[PlanTraceState],
    steps: list[PlanStep],
    dicts: Dictionaries,
) -> Document:
    _intern_features(feature_symbols, dicts)
    return Document(
        header=header,
        sections=[_states_table(states, dicts), _plan_table(steps, dicts)],
    )
