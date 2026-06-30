from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from pyrunir_mcp.kr.ps import proof
from pyrunir_mcp.json_types import JsonObject
from pytyr.formalism.planning import GroundAction

from pyrunir_mcp.kr.ps.proof import CounterexampleKind, ProofResult, StateEvidence, failure_items
from pyrunir_mcp.kr.ps.frontier import format_ground_action
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.planning import LoadedSearchContext
from pyrunir_mcp.tables import Table


def test_format_ground_action_uses_get_objects() -> None:
    action_schema = SimpleNamespace(get_name=lambda: "leave")
    ground_action = SimpleNamespace(
        get_action=lambda: action_schema,
        get_objects=lambda: ["left", "shaker1"],
    )

    assert format_ground_action(cast(GroundAction, ground_action)) == "leave(left, shaker1)"


def test_failure_items_bounds_open_deadends_and_keeps_one_cycle() -> None:
    result = SimpleNamespace(
        cycle=[7, 8, 9],
        open_states=[1, 2, 3],
        deadend_transitions=[10, 11, 12],
    )

    assert failure_items(
        cast(ProofResult, result),
        max_open_state_counterexamples=2,
        max_deadend_transition_counterexamples=1,
    ) == [
        (CounterexampleKind.CYCLE, [7, 8, 9]),
        (CounterexampleKind.OPEN_STATE, 1),
        (CounterexampleKind.OPEN_STATE, 2),
        (CounterexampleKind.DEADEND_TRANSITION, 10),
    ]


def test_failure_items_can_suppress_open_and_deadends_but_not_cycle() -> None:
    result = SimpleNamespace(
        cycle=[7, 8, 9],
        open_states=[1, 2, 3],
        deadend_transitions=[10, 11, 12],
    )

    assert failure_items(
        cast(ProofResult, result),
        max_open_state_counterexamples=0,
        max_deadend_transition_counterexamples=0,
    ) == [(CounterexampleKind.CYCLE, [7, 8, 9])]


def test_build_proof_run_treats_goal_open_state_as_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

    def is_goal_result(observed: object) -> bool:
        return observed is result

    monkeypatch.setattr(proof, "is_goal_open_state_result", is_goal_result)

    def no_tables() -> dict[str, Table]:
        return {}

    envelope = proof.build_proof_run(
        tool="prove_policy",
        output_dir=tmp_path / "out",
        metadata={},
        task=cast(LoadedSearchContext, task),
        result=cast(ProofResult, result),
        feature_symbols=[],
        dicts=cast(Dictionaries, SimpleNamespace(tables=no_tables)),
        ext=False,
    )

    primary = cast(JsonObject, envelope["primary"])

    assert envelope["status"] == "success"
    assert primary["successful"] is True
    assert primary["counterexample_count"] == 0
    assert envelope["items"] == []


def test_failure_items_promotes_classifier_deadend_open_states(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SimpleNamespace(
        cycle=[],
        open_states=[1, 2, 3],
        deadend_transitions=[],
    )
    def is_deadend(observed: ProofResult, vertex: int, evidence: StateEvidence | None) -> bool:
        return vertex == 2

    monkeypatch.setattr(proof, "_open_state_is_deadend", is_deadend)

    assert failure_items(
        cast(ProofResult, result),
        max_open_state_counterexamples=2,
        max_deadend_transition_counterexamples=1,
        evidence=lambda _state: {},
    ) == [
        (CounterexampleKind.DEADEND, 2),
        (CounterexampleKind.OPEN_STATE, 1),
        (CounterexampleKind.OPEN_STATE, 3),
    ]
