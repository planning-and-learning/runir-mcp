from __future__ import annotations

from dataclasses import dataclass
from math import isinf
from datetime import timedelta
from enum import StrEnum
from typing import TypeAlias

from pyrunir.datasets import LiftedTaskSearchContext
from pytyr.planning import ActionCostMode, SearchStatus
from pytyr.planning.ground import State as GroundState
from pytyr.planning.lifted import LMCutHeuristic, Node, State as LiftedState
from pytyr.planning.lifted.astar_eager import Options, find_solution

from pyrunir_mcp.kr.ps.converter import GroundToLiftedStateConverter

class HeuristicSentinel(StrEnum):
    DEADEND = "inf"
    UNKNOWN = ""


HStarValue: TypeAlias = int | float | HeuristicSentinel
LMCutValue: TypeAlias = int | float | HeuristicSentinel


@dataclass(frozen=True)
class HStarOptions:
    max_num_states: int = 100_000
    max_time_seconds: float = 3.0


class HStarEvaluator:
    def __init__(self, search_context: LiftedTaskSearchContext, options: HStarOptions) -> None:
        self._search_context = search_context
        self._options = options
        self._heuristic = LMCutHeuristic(search_context.task, search_context.execution_context)
        self._converter = GroundToLiftedStateConverter(search_context)
        self._hstar_cache: dict[int, HStarValue] = {}
        self._hlmcut_cache: dict[int, LMCutValue] = {}

    def evaluate(self, state: LiftedState | GroundState) -> HStarValue:
        lifted_state = self._lifted_state(state)
        state_index = int(lifted_state.get_index())
        if state_index not in self._hstar_cache:
            self._hstar_cache[state_index] = self._compute(lifted_state)
        return self._hstar_cache[state_index]

    def evaluate_lmcut(self, state: LiftedState | GroundState) -> LMCutValue:
        lifted_state = self._lifted_state(state)
        state_index = int(lifted_state.get_index())
        if state_index not in self._hlmcut_cache:
            self._hlmcut_cache[state_index] = self._compute_lmcut(lifted_state)
        return self._hlmcut_cache[state_index]

    def _lifted_state(self, state: LiftedState | GroundState) -> LiftedState:
        return state if isinstance(state, LiftedState) else self._converter.convert(state)

    def _compute_lmcut(self, state: LiftedState) -> LMCutValue:
        value = float(self._heuristic.evaluate(state))
        if isinf(value):
            return HeuristicSentinel.DEADEND
        return int(value) if value.is_integer() else value

    def _compute(self, state: LiftedState) -> HStarValue:
        options = Options()
        options.start_node = Node(state, 0.0)
        options.max_num_states = self._options.max_num_states
        options.max_time = timedelta(seconds=self._options.max_time_seconds)
        options.action_cost_mode = ActionCostMode.UNIT

        result = find_solution(
            self._search_context.task,
            self._search_context.successor_generator,
            self._heuristic,
            options,
        )
        if result.status == SearchStatus.SOLVED:
            return int(result.plan.get_length())
        if result.status == SearchStatus.UNSOLVABLE:
            return HeuristicSentinel.DEADEND
        return HeuristicSentinel.UNKNOWN
