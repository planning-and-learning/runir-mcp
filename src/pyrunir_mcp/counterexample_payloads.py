from __future__ import annotations

import copy

from pyrunir_mcp.json_types import JsonObject


def _first_int(mapping: JsonObject, keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, int):
            return value
    return None


def state_index(state: JsonObject) -> int | None:
    return _first_int(state, ("state_index", "state_id", "id"))


def vertex_index(state: JsonObject) -> int | None:
    return _first_int(state, ("vertex_index", "vertex_id", "vertex"))


def _state_indices(state: JsonObject) -> tuple[int, ...]:
    indices = []
    for value in (state_index(state), vertex_index(state)):
        if isinstance(value, int) and value not in indices:
            indices.append(value)
    return tuple(indices)


def _states_by_index(states: list[JsonObject]) -> dict[int, JsonObject]:
    result: dict[int, JsonObject] = {}
    for state in states:
        for index in _state_indices(state):
            result.setdefault(index, state)
    return result


def _transition_source(transition: JsonObject) -> int | None:
    return _first_int(
        transition,
        ("source_state_index", "source_vertex_index", "source_state_id", "source_vertex_id", "source_state", "source"),
    )


def _transition_target(transition: JsonObject) -> int | None:
    return _first_int(
        transition,
        ("target_state_index", "target_vertex_index", "target_state_id", "target_vertex_id", "target_state", "target"),
    )


def _transition_index_path(transitions: list[JsonObject]) -> list[int]:
    if not transitions:
        return []
    first = _transition_source(transitions[0])
    if first is None:
        return []
    state_indices = [first]
    for transition in transitions:
        target = _transition_target(transition)
        if target is None:
            return state_indices
        state_indices.append(target)
    return state_indices


def _ordered_states_for_indices(source: JsonObject, state_indices: list[int]) -> list[JsonObject]:
    states = [state for state in source.get("states", []) if isinstance(state, dict)]
    by_index = _states_by_index(states)
    return [copy.deepcopy(by_index[state_index]) for state_index in state_indices if state_index in by_index]


def _path_trace_from_source(
    source: JsonObject,
    witness_state_index: int | None,
    trace_metadata_keys: tuple[str, ...],
) -> JsonObject | None:
    trace = source.get("trace")
    if isinstance(trace, dict):
        return copy.deepcopy(trace)
    transitions = [transition for transition in source.get("transitions", []) if isinstance(transition, dict)]
    if not transitions:
        if witness_state_index is None:
            return None
        trace_data = {
            key: copy.deepcopy(source[key])
            for key in trace_metadata_keys
            if key in source
        }
        trace_data.update(
            {
                "states": _ordered_states_for_indices(source, [witness_state_index]),
                "transitions": [],
                "chosen_actions": [],
                "trace_available": True,
            }
        )
        return trace_data
    state_path = _transition_index_path(transitions)
    if not state_path:
        return None
    if witness_state_index is not None and witness_state_index in state_path:
        stop = state_path.index(witness_state_index)
        transitions = transitions[:stop]
        state_path = state_path[: stop + 1]
    trace_data = {
        key: copy.deepcopy(source[key])
        for key in trace_metadata_keys
        if key in source
    }
    trace_data.update(
        {
            "states": _ordered_states_for_indices(source, state_path),
            "transitions": copy.deepcopy(transitions),
            "chosen_actions": [transition.get("action") for transition in transitions if transition.get("action") is not None],
            "trace_available": True,
        }
    )
    return trace_data


def _cycle_index_path(source: JsonObject, cycle: JsonObject) -> list[int]:
    states = [state for state in source.get("states", []) if isinstance(state, dict)]
    has_vertex_indices = any(vertex_index(state) is not None for state in states)
    preferred_keys = (
        ("cycle_vertex_indices", "cycle_vertex_ids")
        if has_vertex_indices
        else ("cycle_state_indices", "cycle_state_ids")
    )
    for key in preferred_keys:
        indices = [index for index in cycle.get(key, []) if isinstance(index, int)]
        if indices:
            return indices
    return []


def _cycle_counterexample_from_source(source: JsonObject) -> JsonObject | None:
    cycle = source.get("cycle")
    if not isinstance(cycle, dict):
        return None
    cycle_steps = [step for step in cycle.get("cycle_transition_steps", []) if isinstance(step, int)]
    transitions = [transition for transition in source.get("transitions", []) if isinstance(transition, dict)]
    cycle_transitions = [copy.deepcopy(transitions[step]) for step in cycle_steps if 0 <= step < len(transitions)]
    return {
        "cycle": copy.deepcopy(cycle),
        "states": _ordered_states_for_indices(source, _cycle_index_path(source, cycle)),
        "transitions": cycle_transitions,
        "chosen_actions": [transition.get("action") for transition in cycle_transitions if transition.get("action") is not None],
    }


def _witness_state_from_source(source: JsonObject) -> JsonObject | None:
    states = [state for state in source.get("states", []) if isinstance(state, dict)]
    if not states:
        return None
    transitions = [transition for transition in source.get("transitions", []) if isinstance(transition, dict)]
    if transitions:
        target = _transition_target(transitions[-1])
        if target is not None:
            by_index = _states_by_index(states)
            if target in by_index:
                return copy.deepcopy(by_index[target])
    return copy.deepcopy(states[0])


def counterexample_and_trace_payloads(
    source: JsonObject,
    category: str,
    *,
    trace_metadata_keys: tuple[str, ...],
) -> tuple[JsonObject, JsonObject | None]:
    if category == "cycle" or isinstance(source.get("cycle"), dict):
        cycle_payload = _cycle_counterexample_from_source(source)
        if cycle_payload is not None:
            witness_state_index = None
            cycle = cycle_payload.get("cycle")
            if isinstance(cycle, dict):
                cycle_indices = _cycle_index_path(source, cycle)
                if cycle_indices:
                    witness_state_index = cycle_indices[0]
            return cycle_payload, _path_trace_from_source(source, witness_state_index, trace_metadata_keys)
    state = _witness_state_from_source(source)
    payload: JsonObject = {"state": state} if state is not None else {}
    witness_state_index = state_index(state) if isinstance(state, dict) else None
    return payload, _path_trace_from_source(source, witness_state_index, trace_metadata_keys)
