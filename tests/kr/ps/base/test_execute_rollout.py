"""The greedy rollout fallback turns a base `execute` downstream failure into a real multi-step
trace ending at the stuck state (instead of the misleading single init vertex that
`find_ground_solution` reports). See kr/ps/base/rollout.py."""

from __future__ import annotations

import json

# A linear task: setA then setB then setC must all fire on x0 to reach the goal (c x0). The sketch
# only has rules for the first two steps, so the policy advances s0 -> a -> a,b and then dead-ends
# (the only move left, setC, matches no rule).
DOMAIN = """(define (domain seq)
  (:requirements :strips)
  (:predicates (a ?x) (b ?x) (c ?x))
  (:action setA :parameters (?x) :precondition (not (a ?x)) :effect (a ?x))
  (:action setB :parameters (?x) :precondition (and (a ?x) (not (b ?x))) :effect (b ?x))
  (:action setC :parameters (?x) :precondition (and (b ?x) (not (c ?x))) :effect (c ?x)))
"""

PROBLEM = """(define (problem p)
  (:domain seq)
  (:objects x0)
  (:init)
  (:goal (c x0)))
"""

SKETCH = """(:sketch
  (:features
    (:numerical (:symbol na) (:description "count a") (:expression (n_count (c_atomic_state "a"))))
    (:numerical (:symbol nb) (:description "count b") (:expression (n_count (c_atomic_state "b"))))
    (:numerical (:symbol nc) (:description "count c") (:expression (n_count (c_atomic_state "c")))))
  (:rules
    (:rule (:symbol setA) (:description "do a") (:expression (:conditions (:equal_zero na)) (:effects (:increases na))))
    (:rule (:symbol setB) (:description "do b") (:expression (:conditions (:greater_zero na)) (:effects (:increases nb))))))
"""


def _section_rows(text: str, name: str) -> list[str]:
    block = text.split(f"[{name}]", 1)[1].split("\n[", 1)[0]
    lines = [line for line in block.splitlines() if line.strip()]
    return lines[1:]  # drop the column-header line


def _write_task(tmp_path):
    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem = tmp_path / "p.pddl"
    problem.write_text(PROBLEM, encoding="utf-8")
    sketch = tmp_path / "sketch.txt"
    sketch.write_text(SKETCH, encoding="utf-8")
    return domain, problem, sketch


def test_rollout_emits_multistep_trace_to_the_real_stuck_state(tmp_path):
    from pyrunir_mcp.kr.ps.base.execute.service import ExecutePolicyOptions, execute_policy

    domain, problem, sketch = _write_task(tmp_path)
    out = tmp_path / "out"

    result = execute_policy(
        ExecutePolicyOptions(domain_file=domain, problem_file=problem, sketch_file=sketch, num_rollouts=1, dump_dir=out)
    )
    assert not result.is_successful

    trace = (out / "failures" / "open_state-001" / "trace.psv").read_text(encoding="utf-8")
    state_rows = _section_rows(trace, "states")
    transition_rows = _section_rows(trace, "transitions")
    # s0 -> (setA) -> (setB) -> stuck: three states, two committed steps (not a singleton init trace).
    assert len(state_rows) == 3
    assert len(transition_rows) == 2
    assert state_rows[0].split("|")[1] == "INIT"
    assert set(state_rows[-1].split("|")[1].split(",")) == {"OPEN", "WITNESS"}  # terminal stuck state

    # The terminal's frontier shows why it's stuck: its only move (setC) matches no rule (blank rule).
    successors = (out / "failures" / "open_state-001" / "successors.psv").read_text(encoding="utf-8")
    successor_rows = _section_rows(successors, "successors")
    assert successor_rows
    assert all(row.split("|")[3] == "" for row in successor_rows)

    # Everything is local to failures/<id>/, with a machine-readable meta.json indexing the files.
    meta = json.loads((out / "failures" / "open_state-001" / "meta.json").read_text(encoding="utf-8"))
    assert meta["id"] == "open_state-001"
    assert meta["category"] == "open_state"
    assert meta["files"] == {"witness": "witness.psv", "trace": "trace.psv", "successors": "successors.psv"}


def test_classifier_flags_state_as_unsolvable(tmp_path):
    # A real unsolvability classifier is evaluated per state during the rollout. The classifier and the
    # grounding share one parse / repositories (create_execute_context), so this is memory-safe; an
    # `(or (and any))` classifier with `any = (b_nonempty (c_top))` marks every state unsolvable, so
    # the rollout stops at the initial state and flags it DEADEND.
    from pyrunir_mcp.kr.ps.base.execute.service import ExecutePolicyOptions, execute_policy

    domain, problem, sketch = _write_task(tmp_path)
    classifier = tmp_path / "clf.txt"
    classifier.write_text(
        '(:classifier (:symbol c0) (:description "") (:features '
        '(:boolean (:symbol any) (:description "") (:expression (b_nonempty (c_top))))) '
        "(:expression (or (and any))))\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = execute_policy(
        ExecutePolicyOptions(
            domain_file=domain, problem_file=problem, sketch_file=sketch,
            classifier_file=classifier, num_rollouts=1, dump_dir=out,
        )
    )
    assert not result.is_successful
    witness = (out / "failures" / "open_state-001" / "witness.psv").read_text(encoding="utf-8")
    state_rows = _section_rows(witness, "state")
    assert len(state_rows) == 1  # stops immediately: the initial state is classified unsolvable
    assert "DEADEND" in state_rows[0].split("|")[1].split(",")
