"""Internal FF plan traces for reported open states."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from pyrunir.kr import GroundTaskContext
from pytyr.planning import CostMode, SearchStatus
from pytyr.planning.ground import FFRPGHeuristic
from pytyr.planning.ground import Node as GroundNode
from pytyr.planning.ground import State as GroundState
from pytyr.planning.ground.astar_eager import Options, find_solution

from pyrunir_mcp.enums import AtomKind, Flag
from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.kr.ps.feature_evidence import (
    Feature,
    evaluate_features,
    feature_key,
    heuristic_json_value,
    state_atom_evidence,
)
from pyrunir_mcp.kr.ps.frontier import format_ground_action
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HStarOptions
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.plan_trace import PlanStep, PlanTraceState, plan_trace_document
from pyrunir_mcp.tables import Document


def _feature_symbols(features: Sequence[Feature], dicts: Dictionaries) -> list[str]:
    symbols = [feature_key(feature) for feature in features]
    for symbol in symbols:
        dicts.feature(symbol)
    return symbols


def _state_row(
    task_context: GroundTaskContext,
    state: GroundState,
    *,
    features: Sequence[Feature],
    hstar: HStarEvaluator,
    flags: tuple[str, ...] = (),
) -> PlanTraceState:
    atoms = state_atom_evidence(state)
    return PlanTraceState(
        state=int(state.get_index()),
        features=evaluate_features(task_context, state, list(features)),
        fluent=atoms[AtomKind.FLUENT],
        derived=atoms[AtomKind.DERIVED],
        flags=flags,
        hstar=heuristic_json_value(hstar.evaluate(state)),
        hlmcut=heuristic_json_value(hstar.evaluate_lmcut(state)),
    )


def _delta(
    before: dict[str, JsonValue], after: dict[str, JsonValue]
) -> dict[str, tuple[JsonValue, JsonValue]]:
    return {key: (before[key], after[key]) for key in before if key in after and before[key] != after[key]}


def plan_open_state_trace(
    *,
    task_context: GroundTaskContext,
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
    heuristic = FFRPGHeuristic(task_context.search_context.task, task_context.search_context.execution_context)
    options = Options()
    options.start_node = GroundNode(state, 0.0)
    options.max_num_states = effective_max_num_states
    options.max_time = timedelta(seconds=effective_max_time_seconds)
    options.cost_mode = CostMode.UNIT
    result = find_solution(
        task_context.search_context.task,
        task_context.search_context.successor_generator,
        heuristic,
        options,
    )
    if result.status != SearchStatus.SOLVED or result.plan is None:
        return None

    labeled_nodes = result.plan.get_labeled_succ_nodes()
    actions = [format_ground_action(labeled.label) for labeled in labeled_nodes]
    ground_states = [state, *(labeled.node.get_state() for labeled in labeled_nodes)]

    hstar = HStarEvaluator(
        task_context.search_context,
        HStarOptions(max_num_states=effective_max_num_states, max_time_seconds=effective_max_time_seconds),
    )
    state_rows: list[PlanTraceState] = []
    last_index = len(ground_states) - 1
    for index, ground_state in enumerate(ground_states):
        flags: tuple[str, ...]
        if index == 0 and index == last_index:
            flags = (Flag.OPEN, Flag.GOAL)
        elif index == 0:
            flags = (Flag.OPEN,)
        elif index == last_index:
            flags = (Flag.GOAL,)
        else:
            flags = ()
        state_rows.append(
            _state_row(
                task_context,
                ground_state,
                features=features,
                hstar=hstar,
                flags=flags,
            )
        )

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
