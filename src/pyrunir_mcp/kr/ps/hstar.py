from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from math import isinf
from typing import TypeAlias

from pyrunir.datasets import GroundTaskSearchContext, LiftedTaskSearchContext
from pytyr.planning import CostMode, SearchStatus
from pytyr.planning.ground import LMCutHeuristic as GroundLMCutHeuristic
from pytyr.planning.ground import Node as GroundNode
from pytyr.planning.ground import State as GroundState
from pytyr.planning.ground.astar_eager import Options as GroundOptions
from pytyr.planning.ground.astar_eager import find_solution as find_ground_solution
from pytyr.planning.lifted import LMCutHeuristic as LiftedLMCutHeuristic
from pytyr.planning.lifted import Node as LiftedNode
from pytyr.planning.lifted import State as LiftedState
from pytyr.planning.lifted.astar_eager import Options as LiftedOptions
from pytyr.planning.lifted.astar_eager import find_solution as find_lifted_solution

from pyrunir_mcp.enums import HeuristicSentinel
from pyrunir_mcp.kr.ps.converter import GroundToLiftedStateConverter

HStarValue: TypeAlias = int | float | HeuristicSentinel
LMCutValue: TypeAlias = int | float | HeuristicSentinel


@dataclass(frozen=True)
class HStarOptions:
    max_num_states: int = 100_000
    max_time_seconds: float = 3.0


class HStarEvaluator:
    def __init__(self, search_context: GroundTaskSearchContext | LiftedTaskSearchContext, options: HStarOptions) -> None:
        self._options = options
        self._ground_context: GroundTaskSearchContext | None = None
        self._lifted_context: LiftedTaskSearchContext | None = None
        self._ground_heuristic: GroundLMCutHeuristic | None = None
        self._lifted_heuristic: LiftedLMCutHeuristic | None = None
        self._converter: GroundToLiftedStateConverter | None = None
        self._hstar_cache: dict[int, HStarValue] = {}
        self._hlmcut_cache: dict[int, LMCutValue] = {}

        if isinstance(search_context, GroundTaskSearchContext):
            self._ground_context = search_context
            self._ground_heuristic = GroundLMCutHeuristic(search_context.task, search_context.execution_context)
        else:
            self._lifted_context = search_context
            self._lifted_heuristic = LiftedLMCutHeuristic(search_context.task, search_context.execution_context)
            self._converter = GroundToLiftedStateConverter(search_context)

    def evaluate(self, state: LiftedState | GroundState) -> HStarValue:
        state_index = int(state.get_index())
        if state_index not in self._hstar_cache:
            self._hstar_cache[state_index] = self._compute(state)
        return self._hstar_cache[state_index]

    def evaluate_lmcut(self, state: LiftedState | GroundState) -> LMCutValue:
        state_index = int(state.get_index())
        if state_index not in self._hlmcut_cache:
            self._hlmcut_cache[state_index] = self._compute_lmcut(state)
        return self._hlmcut_cache[state_index]

    def _lifted_state(self, state: LiftedState | GroundState) -> LiftedState:
        if isinstance(state, LiftedState):
            return state
        if self._converter is None:
            raise TypeError("Cannot evaluate a lifted heuristic for a ground-only context.")
        return self._converter.convert(state)

    def _ground_state(self, state: LiftedState | GroundState) -> GroundState:
        if isinstance(state, GroundState):
            return state
        raise TypeError("Cannot evaluate a ground heuristic on a lifted state.")

    def _compute_lmcut(self, state: LiftedState | GroundState) -> LMCutValue:
        if self._ground_context is not None and self._ground_heuristic is not None:
            value = float(self._ground_heuristic.evaluate(self._ground_state(state)))
        elif self._lifted_heuristic is not None:
            value = float(self._lifted_heuristic.evaluate(self._lifted_state(state)))
        else:
            return HeuristicSentinel.UNKNOWN
        if isinf(value):
            return HeuristicSentinel.DEADEND
        return int(value) if value.is_integer() else value

    def _compute(self, state: LiftedState | GroundState) -> HStarValue:
        if self._ground_context is not None and self._ground_heuristic is not None:
            options = GroundOptions()
            options.start_node = GroundNode(self._ground_state(state), 0.0)
            options.max_num_states = self._options.max_num_states
            options.max_time = timedelta(seconds=self._options.max_time_seconds)
            options.cost_mode = CostMode.UNIT
            result = find_ground_solution(
                self._ground_context.task,
                self._ground_context.successor_generator,
                self._ground_heuristic,
                options,
            )
        elif self._lifted_context is not None and self._lifted_heuristic is not None:
            options = LiftedOptions()
            options.start_node = LiftedNode(self._lifted_state(state), 0.0)
            options.max_num_states = self._options.max_num_states
            options.max_time = timedelta(seconds=self._options.max_time_seconds)
            options.cost_mode = CostMode.UNIT
            result = find_lifted_solution(
                self._lifted_context.task,
                self._lifted_context.successor_generator,
                self._lifted_heuristic,
                options,
            )
        else:
            return HeuristicSentinel.UNKNOWN

        if result.status == SearchStatus.SOLVED:
            if result.plan is None:
                return HeuristicSentinel.UNKNOWN
            return int(result.plan.get_length())
        if result.status == SearchStatus.UNSOLVABLE:
            return HeuristicSentinel.DEADEND
        return HeuristicSentinel.UNKNOWN
