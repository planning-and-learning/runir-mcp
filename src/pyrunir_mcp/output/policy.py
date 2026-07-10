"""Build policy/module-program witness documents (counterexamples, traces, successors).

Consumes a normalized witness (raw symbols + resolved flags) and the run-global
`Dictionaries`, interning symbols as it builds. Base policy and module-program (ext) share
the same witness shape; ext adds module/memory control context where needed. See the shared
policy/module-program witness output formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from pyrunir_mcp.enums import AtomKind, Flag
from pyrunir_mcp.json_types import JsonValue, normalize_json_value
from pyrunir_mcp.keys import (
    Keys,
    TableColumns,
)
from pyrunir_mcp.output.dictionaries import Dictionaries
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
    memory: tuple[str, str] | None = None  # (module, memory) for ext

@dataclass(frozen=True)
class WitnessTransition:
    step: int
    source: int
    target: int
    source_memory: tuple[str, str] | None = None
    target_memory: tuple[str, str] | None = None
    action: str | None = None
    rule: str | None = None  # raw rule symbol; looked up in the rules dictionary
    delta: dict[str, tuple[JsonValue, JsonValue]] = field(default_factory=_delta_dict)


@dataclass(frozen=True)
class Successor:
    src: int
    target: WitnessState
    source: WitnessState | None = None
    source_memory: tuple[str, str] | None = None  # (module, memory) source control for ext
    action: str | None = None
    rule: str | None = None
    delta: dict[str, tuple[JsonValue, JsonValue]] = field(default_factory=_delta_dict)


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
    normalized = normalize_json_value(value)
    return "T" if normalized is True else "F" if normalized is False else str(normalized)


def _flags(flags: tuple[str, ...]) -> str:
    return ",".join(flags)


def _state_id(index: int) -> str:
    """Planning-state index as a prefixed id (`s42`); planner indices are sparse, so kept verbatim."""
    return f"s{index}"


def _action_alias(symbol: str | None, dicts: Dictionaries) -> str:
    return dicts.action(symbol) if symbol else ""


def _rule_alias(symbol: str | None, dicts: Dictionaries) -> str:
    return (dicts.rule_alias(symbol) or dicts.rule(symbol)) if symbol else ""


def _delta(delta: dict[str, tuple[JsonValue, JsonValue]], dicts: Dictionaries) -> str:
    return " ".join(
        f"{dicts.feature(symbol)}:{_scalar(before)}>{_scalar(after)}"
        for symbol, (before, after) in delta.items()
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
        leading: list[JsonValue] = [
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
    leading: list[str] = [TableColumns.STATE_ID, TableColumns.MODULE_ID, TableColumns.MEMORY_ID, TableColumns.FLAGS] if ext else [TableColumns.STATE_ID, TableColumns.FLAGS]
    if include_hstar:
        leading.append(Keys.HSTAR)
    if include_hlmcut:
        leading.append(Keys.HLMCUT)
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


def _transition_row(transition: WitnessTransition, dicts: Dictionaries, *, ext: bool) -> list[JsonValue]:
    if ext:
        source_module, source_memory = _memory_aliases(transition.source_memory, dicts)
        target_module, target_memory = _memory_aliases(transition.target_memory, dicts)
        return [
            transition.step,
            _state_id(transition.source),
            source_module,
            source_memory,
            _state_id(transition.target),
            target_module,
            target_memory,
            _rule_alias(transition.rule, dicts),
            _action_alias(transition.action, dicts),
            _delta(transition.delta, dicts),
        ]
    return [
        transition.step,
        _state_id(transition.source),
        _state_id(transition.target),
        _rule_alias(transition.rule, dicts),
        _action_alias(transition.action, dicts),
        _delta(transition.delta, dicts),
    ]


def _transitions_table(
    transitions: list[WitnessTransition], dicts: Dictionaries, *, ext: bool
) -> Table:
    rows = [_transition_row(transition, dicts, ext=ext) for transition in transitions]
    return Table(
        name=Keys.TRANSITIONS,
        columns=(
            [
                TableColumns.STEP,
                TableColumns.SOURCE_STATE_ID,
                TableColumns.SOURCE_MODULE_ID,
                TableColumns.SOURCE_MEMORY_ID,
                TableColumns.TARGET_STATE_ID,
                TableColumns.TARGET_MODULE_ID,
                TableColumns.TARGET_MEMORY_ID,
                TableColumns.RULE_ID,
                TableColumns.ACTION_ID,
                TableColumns.DELTAS,
            ]
            if ext
            else [TableColumns.STEP, TableColumns.SOURCE_STATE_ID, TableColumns.TARGET_STATE_ID, TableColumns.RULE_ID, TableColumns.ACTION_ID, TableColumns.DELTAS]
        ),
        rows=rows,
    )


def _successor_row(successor: Successor, dicts: Dictionaries, *, ext: bool) -> list[JsonValue]:
    # Successors are off-graph 1-step moves. For ext, source and target are represented as
    # planning state plus control location. Target control is blank for a gap.
    target = successor.target
    if ext:
        source_module, source_memory = _memory_aliases(successor.source_memory, dicts)
        target_module, target_memory = _memory_aliases(target.memory, dicts)
        return [
            _state_id(successor.src),
            source_module,
            source_memory,
            _action_alias(successor.action, dicts),
            _state_id(target.state),
            target_module,
            target_memory,
            _rule_alias(successor.rule, dicts),
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


def _merge_tuple(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in (*left, *right):
        if item not in seen:
            seen.add(item)
            merged.append(item)
    return tuple(merged)


def _merge_state(existing: WitnessState, incoming: WitnessState) -> WitnessState:
    return WitnessState(
        state=existing.state,
        features={**incoming.features, **existing.features},
        fluent=_merge_tuple(existing.fluent, incoming.fluent),
        derived=_merge_tuple(existing.derived, incoming.derived),
        flags=tuple(flag.value for flag in Flag if flag.value in {*existing.flags, *incoming.flags}),
        hstar=existing.hstar if existing.hstar != "" else incoming.hstar,
        hlmcut=existing.hlmcut if existing.hlmcut != "" else incoming.hlmcut,
        memory=existing.memory if existing.memory is not None else incoming.memory,
    )


def _successor_source_state(successor: Successor) -> WitnessState:
    if successor.source is not None:
        return successor.source
    return WitnessState(successor.src, memory=successor.source_memory)


def _successor_states(successors: list[Successor]) -> list[WitnessState]:
    merged: dict[int, WitnessState] = {}
    for successor in successors:
        for state in (_successor_source_state(successor), successor.target):
            existing = merged.get(state.state)
            merged[state.state] = state if existing is None else _merge_state(existing, state)
    return list(merged.values())


def _successors_table(successors: list[Successor], dicts: Dictionaries, *, ext: bool) -> Table:
    columns: list[str] = (
        [
            TableColumns.SOURCE_STATE_ID,
            TableColumns.SOURCE_MODULE_ID,
            TableColumns.SOURCE_MEMORY_ID,
            TableColumns.ACTION_ID,
            TableColumns.TARGET_STATE_ID,
            TableColumns.TARGET_MODULE_ID,
            TableColumns.TARGET_MEMORY_ID,
            TableColumns.RULE_ID,
            TableColumns.FLAGS,
            TableColumns.DELTAS,
        ]
        if ext
        else [TableColumns.SOURCE_STATE_ID, TableColumns.ACTION_ID, TableColumns.TARGET_STATE_ID, TableColumns.RULE_ID, TableColumns.FLAGS, TableColumns.DELTAS]
    )
    rows = [_successor_row(successor, dicts, ext=ext) for successor in successors]
    return Table(name=Keys.SUCCESSORS, columns=columns, rows=rows)


def _facts_table(states: list[WitnessState], dicts: Dictionaries) -> Table | None:
    rows: list[list[JsonValue]] = []
    seen_states: set[int] = set()
    for state in states:
        if state.state in seen_states:
            continue
        seen_states.add(state.state)
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
    return Table(name=Keys.FACTS, columns=[TableColumns.STATE_ID, TableColumns.ATOM_IDS], rows=rows) if rows else None


def _cycle_state_key(state: WitnessState, *, ext: bool) -> tuple[tuple[int, str], ...]:
    state_key = (state.state, _state_id(state.state))
    if not ext:
        return (state_key,)
    module, memory = state.memory if state.memory is not None else ("", "")
    return ((0, module), (0, memory), state_key)


def _rotate_list(values: list[WitnessState], offset: int) -> list[WitnessState]:
    return values[offset:] + values[:offset]


def _rotate_transitions(values: list[WitnessTransition], offset: int) -> list[WitnessTransition]:
    rotated = values[offset:] + values[:offset]
    return [replace(transition, step=index) for index, transition in enumerate(rotated)]


def _canonical_cycle_payload(
    states: list[WitnessState],
    transitions: list[WitnessTransition],
    *,
    ext: bool,
) -> tuple[list[WitnessState], list[WitnessTransition]]:
    if not states:
        return states, transitions
    offset = min(range(len(states)), key=lambda index: _cycle_state_key(states[index], ext=ext))
    if offset == 0:
        return states, transitions
    return _rotate_list(states, offset), _rotate_transitions(transitions, offset)

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
    cycle: bool,
    dicts: Dictionaries,
    ext: bool,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> Document:
    _intern_features(feature_symbols, dicts)
    if cycle:
        states, transitions = _canonical_cycle_payload(states, transitions, ext=ext)
        cycle_states = [*states, states[0]] if states else states
        sections = [
            _states_table(
                Keys.STATES,
                cycle_states,
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
                Keys.STATES,
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
            Keys.STATES,
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
    states = _successor_states(successors)
    # The `[successors]` rows carry the move + (for ext) its module/memory context. The
    # `[states]`/`[facts]` sections describe every referenced planning state once, including
    # the expanded source state.
    sections = [
        _successors_table(successors, dicts, ext=ext),
        _states_table(
            Keys.STATES,
            states,
            dicts,
            ext=False,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        ),
        _facts_table(states, dicts),
    ]
    return _document(header, sections)
