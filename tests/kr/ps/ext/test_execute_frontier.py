"""End-to-end: an empty module program on a tiny task is stuck, and the successor frontier
(built via the pyrunir `SuccessorExpander`) lists the applicable moves with an empty `rule`
(no module rule selects them = the gap) and blank `module`/`memory` (no move is taken), with a
[facts] section. Columns: source|action|target|rule|module|memory|flags|delta."""

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

EMPTY_PROGRAM = """(:program
    (:entry "empty")
    (:module
        (:symbol empty)
        (:arguments)
        (:description "")
        (:registers)
        (:entry m0)
        (:memory m0)
        (:features)
        (:rules)
    )
)
"""


def _section_rows(text: str, name: str) -> list[str]:
    block = text.split(f"[{name}]", 1)[1].split("\n[", 1)[0]
    lines = [line for line in block.splitlines() if line.strip()]
    return lines[1:]  # drop the column-header line


def test_execute_empty_module_program_emits_trace_and_open_frontier(tmp_path):
    from pyrunir_mcp.kr.ps.ext.execute.service import ExecutePolicyOptions, execute_policy

    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem = tmp_path / "p.pddl"
    problem.write_text(PROBLEM, encoding="utf-8")
    program = tmp_path / "program.txt"
    program.write_text(EMPTY_PROGRAM, encoding="utf-8")
    out = tmp_path / "out"

    result = execute_policy(
        ExecutePolicyOptions(
            domain_file=domain,
            problem_file=problem,
            module_program_file=program,
            num_rollouts=1,
            dump_dir=out,
        )
    )
    assert not result.is_successful  # an empty module program is stuck

    # The witness category may be open_state or cycle; the frontier is emitted either way.
    successors = sorted(out.glob("failures/*/successors.psv"))
    traces = sorted(out.glob("failures/*/trace.psv"))
    assert successors, "expected a successor frontier file"
    assert traces, "expected a trace file"

    successors_text = successors[0].read_text(encoding="utf-8")
    successor_rows = _section_rows(successors_text, "successors")
    assert successor_rows  # the stuck state has applicable moves
    # src|action|tgt|rule|mod|mem|flags|delta -> no module rule selects any move (the gap),
    # so rule + the resulting mod/mem are all blank
    assert all(row.split("|")[3] == "" for row in successor_rows)  # rule
    assert all(row.split("|")[4] == "" and row.split("|")[5] == "" for row in successor_rows)  # mod, mem
    # successor states carry their atoms
    assert _section_rows(successors_text, "facts")
