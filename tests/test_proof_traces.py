from __future__ import annotations

from types import SimpleNamespace

from pyrunir_mcp.kr.ps import proof
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


def test_build_proof_run_treats_goal_open_state_as_success(monkeypatch, tmp_path):
    result = SimpleNamespace(
        graph=SimpleNamespace(),
        cycle=[],
        open_states=[0],
        deadend_transitions=[],
        status=SimpleNamespace(name="FAILURE"),
        is_successful=lambda: False,
    )
    task = SimpleNamespace(problem_path=tmp_path / "p.pddl")
    task.problem_path.write_text("(define (problem p))", encoding="utf-8")

    monkeypatch.setattr(proof, "is_goal_open_state_result", lambda observed: observed is result)

    envelope = proof.build_proof_run(
        tool="prove_policy",
        output_dir=tmp_path / "out",
        metadata={},
        task=task,
        result=result,
        feature_symbols=[],
        dicts=SimpleNamespace(tables=lambda: {}),
        ext=False,
    )

    assert envelope["status"] == "success"
    assert envelope["primary"]["successful"] is True
    assert envelope["primary"]["counterexample_count"] == 0
    assert envelope["items"] == []


def test_failure_items_promotes_classifier_deadend_open_states(monkeypatch):
    result = SimpleNamespace(
        cycle=[],
        open_states=[1, 2, 3],
        deadend_transitions=[],
    )
    monkeypatch.setattr(proof, "_open_state_is_deadend", lambda observed, vertex, evidence: vertex == 2)

    assert failure_items(
        result,
        max_open_state_counterexamples=2,
        max_deadend_transition_counterexamples=1,
        evidence=lambda _state: {},
    ) == [
        (CounterexampleKind.DEADEND, 2),
        (CounterexampleKind.OPEN_STATE, 1),
        (CounterexampleKind.OPEN_STATE, 3),
    ]
