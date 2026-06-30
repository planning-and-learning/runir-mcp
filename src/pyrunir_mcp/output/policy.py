"""Build policy/module-program witness documents (counterexamples, traces, successors).

Consumes a normalized witness (raw symbols + resolved flags) and the run-global
`Dictionaries`, interning symbols as it builds. Base policy and module-program (ext) share
everything; ext adds the `vertex|state|module|memory` columns. See
the shared policy/module-program witness output formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.output.dictionaries import AtomKind, Dictionaries
from pyrunir_mcp.tables import Document, Table


def _json_dict() -> dict[str, JsonValue]:
    return {}


def _delta_dict() -> dict[str, tuple[JsonValue, JsonValue]]:
    return {}


@dataclass(frozen=True)
class WitnessState:
    state: int
    features: dict[str, JsonValue] = field(default_factory=_json_dict)
    fluent: tuple[str, ...] = ()
    derived: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()
    hstar: JsonValue = ""
    hlmcut: JsonValue = ""
    vertex: int | None = None
    memory: tuple[str, str] | None = None  # (module, memory) for ext


@dataclass(frozen=True)
class WitnessTransition:
    step: int
    source: int
    target: int
    action: str | None = None
    rule: str | None = None  # raw rule symbol; looked up in the rules dictionary
    delta: dict[str, tuple[JsonValue, JsonValue]] = field(default_factory=_delta_dict)


@dataclass(frozen=True)
class Cycle:
    state_indices: tuple[int, ...] = ()
    vertex_indices: tuple[int, ...] = ()
    transition_steps: tuple[int, ...] = ()


@dataclass(frozen=True)
class Successor:
    src: int
    target: WitnessState
    action: str | None = None
    rule: str | None = None
    delta: dict[str, tuple[JsonValue, JsonValue]] = field(default_factory=_delta_dict)


class Flag(StrEnum):
    """State markers for the `flags` column in policy/module-program witness output.

    An empty `flags` cell means nothing notable (an unremarkable, alive state) or that the
    status was not evaluated. `DEADEND`/`GOAL` are the status exceptions worth flagging.
    """

    INIT = "INIT"
    GOAL = "GOAL"
    OPEN = "OPEN"
    WITNESS = "WITNESS"
    CYCLE = "CYCLE"
    DEADEND = "DEADEND"


def resolve_flags(
    *,
    initial: bool = False,
    goal: bool = False,
    open_state: bool = False,
    witness: bool = False,
    cycle: bool = False,
    deadend: bool = False,
) -> tuple[Flag, ...]:
    """Map known state roles to flag tokens (empty when nothing notable applies)."""
    return tuple(
        flag
        for present, flag in (
            (initial, Flag.INIT),
            (goal, Flag.GOAL),
            (open_state, Flag.OPEN),
            (witness, Flag.WITNESS),
            (cycle, Flag.CYCLE),
            (deadend, Flag.DEADEND),
        )
        if present
    )


# -- cell helpers --------------------------------------------------------------


def _scalar(value: JsonValue) -> str:
    return "T" if value is True else "F" if value is False else str(value)


def _flags(flags: tuple[str, ...]) -> str:
    return ",".join(flags)


def _state_id(index: int) -> str:
    """Planning-state index as a prefixed id (`s42`); planner indices are sparse, so kept verbatim."""
    return f"s{index}"


def _vertex_id(index: int) -> str:
    """Proof-graph vertex index as a prefixed id (`v3`); vertex indices are already dense per graph."""
    return f"v{index}"


def _state_ids(indices: tuple[int, ...]) -> str:
    return ",".join(_state_id(int(i)) for i in indices)


def _vertex_ids(indices: tuple[int, ...]) -> str:
    return ",".join(_vertex_id(int(i)) for i in indices)


def _steps(indices: tuple[int, ...]) -> str:
    return ",".join(map(str, indices))


def _action_alias(symbol: str | None, dicts: Dictionaries) -> str:
    return dicts.action(symbol) if symbol else ""


def _rule_alias(symbol: str | None, dicts: Dictionaries) -> str:
    return (dicts.rule_alias(symbol) or dicts.rule(symbol)) if symbol else ""


def _delta(delta: dict[str, tuple[JsonValue, JsonValue]], dicts: Dictionaries) -> str:
    return " ".join(
        f"{dicts.feature(s)}:{_scalar(before)}>{_scalar(after)}"
        for s, (before, after) in delta.items()
    )


# -- row + table builders (one `_x_row` / `_x_table` per section) ---------------


def _memory_aliases(memory: tuple[str, str] | None, dicts: Dictionaries) -> tuple[str, str]:
    """(module alias, memory alias) for an ext vertex, or blanks when absent (off-graph / gap)."""
    if not memory:
        return "", ""
    module = dicts.module(memory[0])
    return module, dicts.memory(module, memory[1])


def _state_row(
    state: WitnessState,
    dicts: Dictionaries,
    *,
    ext: bool,
    features: list[str],
    include_hstar: bool,
    include_hlmcut: bool,
) -> list[JsonValue]:
    values = [state.features.get(symbol) for symbol in features]
    if ext:
        module, memory = _memory_aliases(state.memory, dicts)
        vertex = _vertex_id(state.vertex) if state.vertex is not None else ""
        leading: list[JsonValue] = [
            vertex,
            _state_id(state.state),
            module,
            memory,
            _flags(state.flags),
        ]
    else:
        leading = [_state_id(state.state), _flags(state.flags)]
    if include_hstar:
        leading.append(state.hstar)
    if include_hlmcut:
        leading.append(state.hlmcut)
    return [*leading, *values]


def _states_table(
    name: str,
    states: list[WitnessState],
    dicts: Dictionaries,
    *,
    ext: bool,
    include_hstar: bool,
    include_hlmcut: bool,
) -> Table:
    features = dicts.feature_symbols()
    aliases = [f"f{index}" for index in range(len(features))]
    leading = ["vertex", "state", "module", "memory", "flags"] if ext else ["id", "flags"]
    if include_hstar:
        leading.append("hstar")
    if include_hlmcut:
        leading.append("hlmcut")
    rows = [
        _state_row(
            state,
            dicts,
            ext=ext,
            features=features,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        for state in states
    ]
    return Table(name=name, columns=[*leading, *aliases], rows=rows)


def _transition_row(
    transition: WitnessTransition, dicts: Dictionaries, *, ext: bool
) -> list[JsonValue]:
    # Transition endpoints are vertices for ext (a planning state can recur under several memory
    # locations) and planning states for base.
    endpoint = _vertex_id if ext else _state_id
    return [
        transition.step,
        endpoint(transition.source),
        endpoint(transition.target),
        _rule_alias(transition.rule, dicts),
        _action_alias(transition.action, dicts),
        _delta(transition.delta, dicts),
    ]


def _transitions_table(
    transitions: list[WitnessTransition], dicts: Dictionaries, *, ext: bool
) -> Table:
    rows = [_transition_row(transition, dicts, ext=ext) for transition in transitions]
    return Table(
        name="transitions",
        columns=["step", "source", "target", "rule", "action", "delta"],
        rows=rows,
    )


def _successor_row(successor: Successor, dicts: Dictionaries, *, ext: bool) -> list[JsonValue]:
    # Successors are off-graph 1-step moves, so source/target are planning states. For ext,
    # module/memory carry the resulting memory the selecting rule lands in (blank for a gap).
    target = successor.target
    if ext:
        module, memory = _memory_aliases(target.memory, dicts)
        return [
            _state_id(successor.src),
            _action_alias(successor.action, dicts),
            _state_id(target.state),
            _rule_alias(successor.rule, dicts),
            module,
            memory,
            _flags(target.flags),
            _delta(successor.delta, dicts),
        ]
    return [
        _state_id(successor.src),
        _action_alias(successor.action, dicts),
        _state_id(target.state),
        _rule_alias(successor.rule, dicts),
        _flags(target.flags),
        _delta(successor.delta, dicts),
    ]


def _successors_table(successors: list[Successor], dicts: Dictionaries, *, ext: bool) -> Table:
    columns = (
        ["source", "action", "target", "rule", "module", "memory", "flags", "delta"]
        if ext
        else ["source", "action", "target", "rule", "flags", "delta"]
    )
    rows = [_successor_row(successor, dicts, ext=ext) for successor in successors]
    return Table(name="successors", columns=columns, rows=rows)


def _facts_table(states: list[WitnessState], dicts: Dictionaries) -> Table | None:
    rows: list[list[JsonValue]] = []
    for state in states:
        # Atoms are interned in first-appearance order, so a state's list would otherwise read in
        # an arbitrary order (e.g. p12 before p1). Sort each row by alias index for a stable,
        # readable `p0,p1,p2,…` ordering that aligns across states.
        aliases = [
            dicts.atom(kind, atom)
            for kind, group in ((AtomKind.FLUENT, state.fluent), (AtomKind.DERIVED, state.derived))
            for atom in group
        ]
        if aliases:
            aliases.sort(key=lambda alias: int(alias[1:]))
            rows.append([_state_id(state.state), ",".join(aliases)])
    return Table(name="facts", columns=["state", "atoms"], rows=rows) if rows else None


def _cycle_table(cycle: Cycle, *, ext: bool) -> Table:
    rows: list[list[JsonValue]] = []
    if ext and cycle.vertex_indices:
        rows.append(["cycle_vertex_indices", _vertex_ids(cycle.vertex_indices)])
    if cycle.state_indices:
        rows.append(["cycle_state_indices", _state_ids(cycle.state_indices)])
    if cycle.transition_steps:
        rows.append(["cycle_transition_steps", _steps(cycle.transition_steps)])
    return Table(name="cycle", columns=["key", "value"], rows=rows)


# -- documents (each: intern features first, assemble sections, drop empty ones) --


def _document(header: list[tuple[str, str]], sections: list[Table | None]) -> Document:
    return Document(
        header=header, sections=[section for section in sections if section is not None]
    )


def _intern_features(features: list[str], dicts: Dictionaries) -> None:
    """Fix the `f0,f1,…` column order before any `[states]` table is built."""
    for symbol in features:
        dicts.feature(symbol)


def counterexample_document(
    *,
    header: list[tuple[str, str]],
    feature_symbols: list[str],
    states: list[WitnessState],
    transitions: list[WitnessTransition],
    cycle: Cycle | None,
    dicts: Dictionaries,
    ext: bool,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> Document:
    _intern_features(feature_symbols, dicts)
    if cycle is not None:
        sections = [
            _cycle_table(cycle, ext=ext),
            _states_table(
                "states",
                states,
                dicts,
                ext=ext,
                include_hstar=include_hstar,
                include_hlmcut=include_hlmcut,
            ),
            _transitions_table(transitions, dicts, ext=ext),
        ]
    else:
        sections = [
            _states_table(
                "state",
                states,
                dicts,
                ext=ext,
                include_hstar=include_hstar,
                include_hlmcut=include_hlmcut,
            )
        ]
    return _document(header, [*sections, _facts_table(states, dicts)])


def trace_document(
    *,
    header: list[tuple[str, str]],
    feature_symbols: list[str],
    states: list[WitnessState],
    transitions: list[WitnessTransition],
    dicts: Dictionaries,
    ext: bool,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> Document:
    _intern_features(feature_symbols, dicts)
    sections = [
        _states_table(
            "states",
            states,
            dicts,
            ext=ext,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        ),
        _transitions_table(transitions, dicts, ext=ext),
        _facts_table(states, dicts),
    ]
    return _document(header, sections)


def successors_document(
    *,
    header: list[tuple[str, str]],
    feature_symbols: list[str],
    successors: list[Successor],
    dicts: Dictionaries,
    ext: bool,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> Document:
    _intern_features(feature_symbols, dicts)
    targets = [successor.target for successor in successors]
    # The `[successors]` rows carry the move + (for ext) its `mod`/`mem`; the target `[states]`
    # sub-table is just the off-graph successor states' feature values, so it stays state-indexed.
    sections = [
        _successors_table(successors, dicts, ext=ext),
        _states_table(
            "states",
            targets,
            dicts,
            ext=False,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        ),
        _facts_table(targets, dicts),
    ]
    return _document(header, sections)
