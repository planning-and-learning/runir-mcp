from __future__ import annotations

from pathlib import Path

from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.kr.ps.plan_trace import plan_open_state_trace
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.plan_trace import PlanStep, PlanTraceState, plan_trace_document
from pyrunir_mcp.planning import build_ground_search_context
from pyrunir_mcp.tables import render_document

DOMAIN = """(define (domain seq)
  (:requirements :strips)
  (:predicates (fixed ?x) (a ?x) (b ?x))
  (:action setA :parameters (?x) :precondition (and (fixed ?x) (not (a ?x))) :effect (a ?x))
  (:action setB :parameters (?x) :precondition (and (fixed ?x) (a ?x) (not (b ?x))) :effect (b ?x)))
"""

PROBLEM = """(define (problem p)
  (:domain seq)
  (:objects x0)
  (:init (fixed x0))
  (:goal (b x0)))
"""


def _write_task(tmp_path: Path) -> tuple[Path, Path]:
    domain = tmp_path / "domain.pddl"
    problem = tmp_path / "problem.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem.write_text(PROBLEM, encoding="utf-8")
    return domain, problem


def test_plan_open_state_trace_uses_ff_plan_and_shared_action_dictionary(tmp_path: Path) -> None:
    domain, problem = _write_task(tmp_path)
    execution_context = ExecutionContext(1)
    ground = build_ground_search_context(domain, problem, execution_context)
    dicts = Dictionaries(task=ground.task)
    dicts.action("preexisting")

    doc = plan_open_state_trace(
        ground_context=ground,
        state=ground.state_repository.get_initial_state(),
        features=[],
        dicts=dicts,
        max_num_states=100,
        max_time_seconds=3.0,
    )

    assert doc is not None
    assert render_document(doc, "psv") == (
        "[states]\nstate_id|flags|hstar|hlmcut\ns0|open|2|2\ns1||1|1\ns2|goal|0|0\n"
        "\n[plan]\nstep|source_state_id|action_id|target_state_id|deltas\n0|s0|a1|s1|\n1|s1|a2|s2|\n"
        "\n[facts]\nstate_id|atom_ids\ns1|p2\ns2|p2,p3"
    )
    assert dicts.tables()["actions"].rows == [
        ["a0", "preexisting"],
        ["a1", "seta(x0)"],
        ["a2", "setb(x0)"],
    ]
    assert dicts.tables()["atoms"].rows == [
        ["p0", "static_atoms", "(fixed x0)"],
        ["p1", "static_atoms", "(object x0)"],
        ["p2", "fluent_atoms", "(a x0)"],
        ["p3", "fluent_atoms", "(b x0)"],
    ]


def test_plan_trace_plan_rows_show_feature_deltas() -> None:
    dicts = Dictionaries()
    doc = plan_trace_document(
        header=[],
        feature_symbols=["remaining", "ready"],
        states=[
            PlanTraceState(0, {"remaining": 2, "ready": False}, flags=("open",)),
            PlanTraceState(1, {"remaining": 1, "ready": True}),
            PlanTraceState(2, {"remaining": 0, "ready": True}, flags=("goal",)),
        ],
        steps=[
            PlanStep(0, 0, "advance", 1, {"remaining": (2, 1), "ready": (False, True)}),
            PlanStep(1, 1, "finish", 2, {"remaining": (1, 0)}),
        ],
        dicts=dicts,
    )

    assert render_document(doc, "psv") == (
        "[states]\nstate_id|flags|hstar|hlmcut|f0|f1\ns0|open|||2|F\ns1||||1|T\ns2|goal|||0|T\n"
        "\n[plan]\nstep|source_state_id|action_id|target_state_id|deltas\n0|s0|a0|s1|f0:2>1 f1:F>T\n1|s1|a1|s2|f0:1>0"
    )


def test_plan_trace_uint32_max_feature_values_render_as_inf() -> None:
    dicts = Dictionaries()
    doc = plan_trace_document(
        header=[],
        feature_symbols=["n"],
        states=[
            PlanTraceState(45, {"n": 2**32 - 1}, flags=("open",)),
            PlanTraceState(46, {"n": 1}, flags=("goal",)),
        ],
        steps=[PlanStep(0, 45, "advance", 46, {"n": (2**32 - 1, 1)})],
        dicts=dicts,
    )

    psv = render_document(doc, "psv")
    assert "s45|open|||inf" in psv
    assert "f0:inf>1" in psv
