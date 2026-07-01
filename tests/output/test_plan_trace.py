from __future__ import annotations

from pathlib import Path

from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.kr.ps.plan_trace import plan_open_state_trace
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.planning import build_ground_search_context, load_lifted_search_context
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
    lifted = load_lifted_search_context(domain, problem, execution_context).search_context
    dicts = Dictionaries()
    dicts.action("preexisting")

    doc = plan_open_state_trace(
        ground_context=ground,
        lifted_context=lifted,
        state=ground.state_repository.get_initial_state(),
        features=[],
        dicts=dicts,
        max_num_states=100,
        max_time_seconds=3.0,
    )

    assert doc is not None
    assert render_document(doc, "psv") == (
        "[states]\nstate|flags|hstar|hlmcut\ns0|OPEN|2|2\ns1||1|1\ns2|GOAL|0|0\n"
        "\n[plan]\nstep|source|action|target|delta\n0|s0|a1|s1|\n1|s1|a2|s2|"
    )
    assert dicts.tables()["actions"].rows == [
        ["a0", "preexisting"],
        ["a1", "seta(x0)"],
        ["a2", "setb(x0)"],
    ]
    assert dicts.tables()["atoms"].rows == [
        ["p0", "static", "(fixed x0)"],
        ["p1", "static", "(object x0)"],
        ["p2", "fluent", "(a x0)"],
        ["p3", "fluent", "(b x0)"],
    ]
