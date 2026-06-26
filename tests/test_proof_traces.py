from __future__ import annotations

from types import SimpleNamespace

from pyrunir_mcp.kr.ps.proof import CounterexampleKind, _format_ground_action, failure_items


def test_format_ground_action_uses_get_objects():
    action_schema = SimpleNamespace(get_name=lambda: "leave")
    ground_action = SimpleNamespace(
        get_action=lambda: action_schema,
        get_objects=lambda: ["left", "shaker1"],
    )

    assert _format_ground_action(ground_action) == "leave(left, shaker1)"


def test_failure_items_bounds_open_deadends_and_keeps_one_cycle():
    result = SimpleNamespace(
        cycle=[7, 8, 9],
        open_states=[1, 2, 3],
        deadend_transitions=[10, 11, 12],
    )

    assert failure_items(
        result,
        max_open_state_counterexamples=2,
        max_deadend_transition_counterexamples=1,
    ) == [
        (CounterexampleKind.CYCLE, [7, 8, 9]),
        (CounterexampleKind.OPEN_STATE, 1),
        (CounterexampleKind.OPEN_STATE, 2),
        (CounterexampleKind.DEADEND_TRANSITION, 10),
    ]


def test_failure_items_can_suppress_open_and_deadends_but_not_cycle():
    result = SimpleNamespace(
        cycle=[7, 8, 9],
        open_states=[1, 2, 3],
        deadend_transitions=[10, 11, 12],
    )

    assert failure_items(
        result,
        max_open_state_counterexamples=0,
        max_deadend_transition_counterexamples=0,
    ) == [(CounterexampleKind.CYCLE, [7, 8, 9])]
