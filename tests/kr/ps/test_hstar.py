from __future__ import annotations

from pathlib import Path

from pytyr.planning.ground import Node as GroundNode
from pytyr.planning.lifted import Node
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.enums import HeuristicSentinel
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HStarOptions
from pyrunir_mcp.planning import build_ground_search_context, load_lifted_search_context

DOMAIN = """(define (domain seq)
  (:requirements :strips)
  (:predicates (a ?x) (b ?x))
  (:action setA :parameters (?x) :precondition (not (a ?x)) :effect (a ?x))
  (:action setB :parameters (?x) :precondition (and (a ?x) (not (b ?x))) :effect (b ?x)))
"""

PROBLEM = """(define (problem p)
  (:domain seq)
  (:objects x0)
  (:init)
  (:goal (b x0)))
"""

UNSOLVABLE_DOMAIN = """(define (domain stuck)
  (:requirements :strips)
  (:predicates (goal))
  (:action noop :parameters () :precondition (goal) :effect (goal)))
"""

UNSOLVABLE_PROBLEM = """(define (problem p)
  (:domain stuck)
  (:init)
  (:goal (goal)))
"""


def _write_task(tmp_path: Path, domain_text: str, problem_text: str) -> tuple[Path, Path]:
    domain = tmp_path / "domain.pddl"
    problem = tmp_path / "problem.pddl"
    domain.write_text(domain_text, encoding="utf-8")
    problem.write_text(problem_text, encoding="utf-8")
    return domain, problem


def test_hstar_uses_lifted_start_state_option(tmp_path: Path) -> None:
    domain, problem = _write_task(tmp_path, DOMAIN, PROBLEM)
    context = load_lifted_search_context(domain, problem, ExecutionContext(1)).search_context
    evaluator = HStarEvaluator(context, HStarOptions(max_num_states=100, max_time_seconds=3.0))

    initial = context.state_repository.get_initial_state()
    first_successors = context.successor_generator.get_labeled_successor_nodes(Node(initial, 0.0))
    after_first = first_successors[0].node.get_state()
    second_successors = context.successor_generator.get_labeled_successor_nodes(Node(after_first, 0.0))
    goal = second_successors[0].node.get_state()

    assert evaluator.evaluate(initial) == 2
    assert evaluator.evaluate(after_first) == 1
    assert evaluator.evaluate(goal) == 0
    assert evaluator.evaluate_lmcut(initial) == 2
    assert evaluator.evaluate_lmcut(after_first) == 1
    assert evaluator.evaluate_lmcut(goal) == 0


def test_hstar_marks_lifted_deadend_as_inf(tmp_path: Path) -> None:
    domain, problem = _write_task(tmp_path, UNSOLVABLE_DOMAIN, UNSOLVABLE_PROBLEM)
    context = load_lifted_search_context(domain, problem, ExecutionContext(1)).search_context
    evaluator = HStarEvaluator(context, HStarOptions(max_num_states=100, max_time_seconds=3.0))

    initial = context.state_repository.get_initial_state()
    assert evaluator.evaluate(initial) == HeuristicSentinel.DEADEND
    assert evaluator.evaluate_lmcut(initial) == HeuristicSentinel.DEADEND


def test_hstar_converts_ground_state_into_lifted_repository(tmp_path: Path) -> None:
    domain, problem = _write_task(tmp_path, DOMAIN, PROBLEM)
    execution_context = ExecutionContext(1)
    lifted = load_lifted_search_context(domain, problem, execution_context).search_context
    ground = build_ground_search_context(domain, problem, execution_context)
    evaluator = HStarEvaluator(lifted, HStarOptions(max_num_states=100, max_time_seconds=3.0))

    ground_initial = ground.state_repository.get_initial_state()
    ground_after_first = ground.successor_generator.get_labeled_successor_nodes(GroundNode(ground_initial, 0.0))[0].node.get_state()

    assert evaluator.evaluate(ground_initial) == 2
    assert evaluator.evaluate(ground_after_first) == 1
    assert evaluator.evaluate_lmcut(ground_initial) == 2
    assert evaluator.evaluate_lmcut(ground_after_first) == 1


def test_hstar_budget_exhaustion_is_unknown_not_inf(tmp_path: Path) -> None:
    domain, problem = _write_task(tmp_path, DOMAIN, PROBLEM)
    context = load_lifted_search_context(domain, problem, ExecutionContext(1)).search_context
    evaluator = HStarEvaluator(context, HStarOptions(max_num_states=0, max_time_seconds=3.0))

    assert evaluator.evaluate(context.state_repository.get_initial_state()) == HeuristicSentinel.UNKNOWN
