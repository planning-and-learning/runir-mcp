"""End-to-end: an empty policy on a tiny task yields a singleton open-state trace and a
successor frontier whose rule column is empty (no rule selects any move = the gap)."""

from __future__ import annotations

DOMAIN = """(define (domain tiny)
  (:requirements :strips)
  (:predicates (at ?x))
  (:action go
    :parameters (?from ?to)
    :precondition (at ?from)
    :effect (and (not (at ?from)) (at ?to))))
"""

PROBLEM = """(define (problem p)
  (:domain tiny)
  (:objects a b)
  (:init (at a))
  (:goal (at b)))
"""

EMPTY_SKETCH = "(:sketch (:features) (:rules))\n"


def _section_rows(text: str, name: str) -> list[str]:
    block = text.split(f"[{name}]", 1)[1].split("\n[", 1)[0]
    lines = [line for line in block.splitlines() if line.strip()]
    return lines[1:]  # drop the column-header line


def test_execute_empty_policy_emits_singleton_trace_and_open_frontier(tmp_path):
    from pyrunir_mcp.kr.ps.base.execute.service import ExecutePolicyOptions, execute_policy

    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem = tmp_path / "p.pddl"
    problem.write_text(PROBLEM, encoding="utf-8")
    sketch = tmp_path / "sketch.txt"
    sketch.write_text(EMPTY_SKETCH, encoding="utf-8")
    out = tmp_path / "out"

    result = execute_policy(
        ExecutePolicyOptions(
            domain_file=domain,
            problem_file=problem,
            sketch_file=sketch,
            num_rollouts=1,
            dump_dir=out,
        )
    )
    assert not result.is_successful  # an empty policy is stuck at the initial state

    trace = out / "failures" / "open_state-001" / "trace.psv"
    successors = out / "failures" / "open_state-001" / "successors.psv"
    assert trace.is_file()
    assert successors.is_file()

    trace_text = trace.read_text(encoding="utf-8")
    assert len(_section_rows(trace_text, "states")) == 1  # singleton trace
    assert _section_rows(trace_text, "transitions") == []  # no chosen action

    successors_text = successors.read_text(encoding="utf-8")
    successor_rows = _section_rows(successors_text, "successors")
    assert successor_rows  # the open state has applicable moves
    # src|action|tgt|rule|flags|delta -> the rule cell is empty for every move (the gap)
    assert all(row.split("|")[3] == "" for row in successor_rows)
    # successor states carry their atoms (a [facts] section), like the trace/counterexample
    assert _section_rows(successors_text, "facts")



def test_execute_empty_policy_can_disable_hstar_and_hlmcut_columns(tmp_path):
    from pyrunir_mcp.kr.ps.base.execute.service import ExecutePolicyOptions, execute_policy

    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem = tmp_path / "p.pddl"
    problem.write_text(PROBLEM, encoding="utf-8")
    sketch = tmp_path / "sketch.txt"
    sketch.write_text(EMPTY_SKETCH, encoding="utf-8")

    lmcut_only = tmp_path / "lmcut-only"
    execute_policy(
        ExecutePolicyOptions(
            domain_file=domain,
            problem_file=problem,
            sketch_file=sketch,
            num_rollouts=1,
            include_hstar=False,
            include_hlmcut=True,
            dump_dir=lmcut_only,
        )
    )
    text = (lmcut_only / "failures" / "open_state-001" / "successors.psv").read_text(encoding="utf-8")
    assert "[states]\nid|flags|hlmcut" in text
    assert "hstar" not in text

    no_heuristics = tmp_path / "no-heuristics"
    execute_policy(
        ExecutePolicyOptions(
            domain_file=domain,
            problem_file=problem,
            sketch_file=sketch,
            num_rollouts=1,
            include_hstar=False,
            include_hlmcut=False,
            dump_dir=no_heuristics,
        )
    )
    text = (no_heuristics / "failures" / "open_state-001" / "successors.psv").read_text(encoding="utf-8")
    assert "hstar" not in text
    assert "hlmcut" not in text

def test_execute_empty_policy_on_initial_goal_does_not_emit_open_state(tmp_path):
    from pyrunir_mcp.kr.ps.base.execute.service import ExecutePolicyOptions, execute_policy

    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem = tmp_path / "p.pddl"
    problem.write_text("""(define (problem p)
  (:domain tiny)
  (:objects a b)
  (:init (at a))
  (:goal (at a)))
""", encoding="utf-8")
    sketch = tmp_path / "sketch.txt"
    sketch.write_text(EMPTY_SKETCH, encoding="utf-8")
    out = tmp_path / "out"

    result = execute_policy(
        ExecutePolicyOptions(
            domain_file=domain,
            problem_file=problem,
            sketch_file=sketch,
            num_rollouts=1,
            dump_dir=out,
        )
    )

    assert result.is_successful
    assert not (out / "failures" / "open_state-001").exists()
    manifest_text = (out / "manifest.json").read_text(encoding="utf-8")
    assert '"status": "SUCCESS"' in manifest_text
    assert '"successful_traces"' in manifest_text
    assert (out / "successes" / "success-001" / "trace.psv").is_file()
    assert (out / "successes" / "success-001" / "meta.json").is_file()
    assert (out / "successes.psv").is_file()
