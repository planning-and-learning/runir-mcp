from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from pytyr.formalism.planning import GroundAction

from pyrunir_mcp.enums import CounterexampleKind
from pyrunir_mcp.kr.ps.frontier import format_ground_action
from pyrunir_mcp.kr.ps.proof import ProofResult, failure_items


def test_format_ground_action_uses_get_objects() -> None:
    action_schema = SimpleNamespace(get_name=lambda: "leave")
    ground_action = SimpleNamespace(
        get_action=lambda: action_schema,
        get_objects=lambda: ["left", "shaker1"],
    )

    assert format_ground_action(cast(GroundAction, ground_action)) == "leave(left, shaker1)"


def test_failure_items_bounds_deadends_and_keeps_one_cycle() -> None:
    result = SimpleNamespace(
        cycle=[7, 8, 9],
        open_states=[1, 2, 3],
        deadend_states=[10, 11, 12],
    )

    assert failure_items(
        cast(ProofResult, result),
        max_counterexamples=3,
    ) == [
        (CounterexampleKind.CYCLE, [7, 8, 9]),
        (CounterexampleKind.DEADEND, 10),
        (CounterexampleKind.DEADEND, 11),
        (CounterexampleKind.DEADEND, 12),
    ]


def test_failure_items_can_suppress_deadends_and_open_states_but_not_cycle() -> None:
    result = SimpleNamespace(
        cycle=[7, 8, 9],
        open_states=[1, 2, 3],
        deadend_states=[10, 11, 12],
    )

    assert failure_items(
        cast(ProofResult, result),
        max_counterexamples=0,
    ) == [(CounterexampleKind.CYCLE, [7, 8, 9])]


def test_failure_items_uses_native_deadend_and_open_state_partition() -> None:
    result = SimpleNamespace(
        cycle=[],
        deadend_states=[2],
        open_states=[1, 3],
    )

    assert failure_items(
        cast(ProofResult, result),
        max_counterexamples=2,
    ) == [
        (CounterexampleKind.DEADEND, 2),
        (CounterexampleKind.OPEN_STATE, 1),
    ]
