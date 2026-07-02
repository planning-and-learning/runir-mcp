"""Internal FF plan traces for reported open states."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from pyrunir.datasets import GroundTaskSearchContext, LiftedTaskSearchContext
from pytyr.planning import ActionCostMode, SearchStatus
from pytyr.planning.ground import Node as GroundNode, State as GroundState
from pytyr.planning.lifted import FFRPGHeuristic, Node as LiftedNode
from pytyr.planning.lifted.astar_eager import Options, find_solution

from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.kr.ps.converter import GroundToLiftedStateConverter
from pyrunir_mcp.kr.ps.feature_evidence import (
    Feature,
    evaluate_features,
    feature_key,
    heuristic_json_value,
    state_atom_evidence,
    state_facts,
)
from pyrunir_mcp.kr.ps.frontier import format_ground_action
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HStarOptions
from pyrunir_mcp.output.dictionaries import AtomKind, Dictionaries
from pyrunir_mcp.output.plan_trace import PlanStep, PlanTraceState, plan_trace_document
from pyrunir_mcp.tables import Document


def _feature_symbols(features: Sequence[Feature], dicts: Dictionaries) -> list[str]:
    symbols = [feature_key(feature) for feature in features]
    for symbol in symbols:
        dicts.feature(symbol)
    return symbols


def _intern_state_atoms(state: GroundState, dicts: Dictionaries) -> None:
    for kind, atom in state_atom_evidence(state):
        dicts.atom(AtomKind(kind), atom)


def _state_row(
    state: GroundState,
    *,
    features: Sequence[Feature],
    hstar: HStarEvaluator,
    flags: tuple[str, ...] = (),
) -> PlanTraceState:
    facts = state_facts(state)
    fluent_facts = facts.get("fluent_facts", [])
    derived_atoms = facts.get("derived_atoms", [])
    return PlanTraceState(
        state=int(state.get_index()),
        features=evaluate_features(state, list(features)),
        fluent=tuple(str(atom) for atom in fluent_facts) if isinstance(fluent_facts, list) else (),
        derived=tuple(str(atom) for atom in derived_atoms) if isinstance(derived_atoms, list) else (),
        flags=flags,
        hstar=heuristic_json_value(hstar.evaluate(state)),
        hlmcut=heuristic_json_value(hstar.evaluate_lmcut(state)),
    )


def _delta(
    before: dict[str, JsonValue], after: dict[str, JsonValue]
) -> dict[str, tuple[JsonValue, JsonValue]]:
    return {key: (before[key], after[key]) for key in before if key in after and before[key] != after[key]}


def _replay_ground_plan(
    ground_context: GroundTaskSearchContext,
    start: GroundState,
    actions: list[str],
) -> list[GroundState] | None:
    states = [start]
    current = start
    for action in actions:
        successors = ground_context.successor_generator.get_labeled_successor_nodes(
            GroundNode(current, 0.0)
        )
        match = next(
            (
                labeled.node.get_state()
                for labeled in successors
                if format_ground_action(labeled.label) == action
            ),
            None,
        )
        if match is None:
            return None
        states.append(match)
        current = match
    return states


def plan_open_state_trace(
    *,
    ground_context: GroundTaskSearchContext,
    lifted_context: LiftedTaskSearchContext,
    state: GroundState,
    features: Sequence[Feature],
    dicts: Dictionaries,
    max_num_states: int | None = 1_000_000,
    max_time_seconds: float | None = 10.0,
) -> Document | None:
    """Return a headerless FF plan trace from an open ground state, or None if no plan is found."""
    feature_symbols = _feature_symbols(features, dicts)
    effective_max_num_states = max_num_states if max_num_states is not None else 1_000_000
    effective_max_time_seconds = max_time_seconds if max_time_seconds is not None else 10.0
    lifted_state = GroundToLiftedStateConverter(lifted_context).convert(state)
    heuristic = FFRPGHeuristic(lifted_context.task, lifted_context.execution_context)
    options = Options()
    options.start_node = LiftedNode(lifted_state, 0.0)
    options.max_num_states = effective_max_num_states
    options.max_time = timedelta(seconds=effective_max_time_seconds)
    options.action_cost_mode = ActionCostMode.UNIT
    result = find_solution(
        lifted_context.task,
        lifted_context.successor_generator,
        heuristic,
        options,
    )
    if result.status != SearchStatus.SOLVED or result.plan is None:
        return None

    actions = [format_ground_action(labeled.label) for labeled in result.plan.get_labeled_succ_nodes()]
    ground_states = _replay_ground_plan(ground_context, state, actions)
    if ground_states is None:
        return None

    hstar = HStarEvaluator(
        lifted_context,
        HStarOptions(max_num_states=effective_max_num_states, max_time_seconds=effective_max_time_seconds),
    )
    state_rows: list[PlanTraceState] = []
    last_index = len(ground_states) - 1
    for index, ground_state in enumerate(ground_states):
        _intern_state_atoms(ground_state, dicts)
        flags: tuple[str, ...]
        if index == 0 and index == last_index:
            flags = ("OPEN", "GOAL")
        elif index == 0:
            flags = ("OPEN",)
        elif index == last_index:
            flags = ("GOAL",)
        else:
            flags = ()
        state_rows.append(_state_row(ground_state, features=features, hstar=hstar, flags=flags))

    steps = [
        PlanStep(
            step=index,
            source=int(source.state),
            action=actions[index],
            target=int(target.state),
            delta=_delta(source.features, target.features),
        )
        for index, (source, target) in enumerate(zip(state_rows, state_rows[1:]))
    ]
    return plan_trace_document(
        header=[],
        feature_symbols=feature_symbols,
        states=state_rows,
        steps=steps,
        dicts=dicts,
    )
