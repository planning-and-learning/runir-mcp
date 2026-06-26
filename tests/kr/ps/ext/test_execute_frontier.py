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
    (:entry empty)
    (:module
        (:symbol empty)
        (:arguments)
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


PROGRAM_WITH_VARIANT_SYMBOL_RULES = """(:program
    (:entry main)
    (:module
        (:symbol main)
        (:arguments)
        (:registers
            (:concept r0)
        )
        (:entry source)
        (:memory
            source
            target
        )
        (:features
            (:numerical
                (:symbol reachable-count)
                (:expression (n_count (c_top)))
            )
        )
        (:rules
            (:rule
                (:symbol load-edge)
                        (:expression
                    (:source-memory source)
                    (:target-memory target)
                    (:load
                        (:conditions)
                        (:concept (c_top))
                        (:register
                            (:concept r0)
                        )
                    )
                )
            )
            (:rule
                (:symbol sketch-edge)
                        (:expression
                    (:source-memory target)
                    (:target-memory target)
                    (:sketch
                        (:conditions)
                        (:effects)
                    )
                )
            )
        )
    )
)
"""


def test_ext_intern_rules_uses_rule_variant_symbols(tmp_path):
    from pyrunir_mcp.kr.ps.ext.core.features import create_module_program_context
    from pyrunir_mcp.kr.ps.ext.core.policy_io import parse_module_program_description
    from pyyggdrasil.execution import ExecutionContext
    from pyrunir_mcp.kr.ps.ext.core.data_loader import load_grounded_search_context
    from pyrunir_mcp.kr.ps.ext.rules import collect_features, intern_rules
    from pyrunir_mcp.kr.ps.feature_evidence import evaluate_features
    from pyrunir_mcp.output.dictionaries import Dictionaries

    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")

    context = create_module_program_context(domain)
    program = parse_module_program_description(context, PROGRAM_WITH_VARIANT_SYMBOL_RULES)
    dicts = Dictionaries(ext=True)

    intern_rules(program, dicts)

    assert dicts.rule_alias("load-edge") == "r0"
    assert dicts.rule_alias("sketch-edge") == "r1"
    assert dicts.tables()["rules"].rows == [
        ["r0", "load-edge", "m0", "m1"],
        ["r1", "sketch-edge", "m1", "m1"],
    ]

    problem = tmp_path / "p.pddl"
    problem.write_text(PROBLEM, encoding="utf-8")
    search_context = load_grounded_search_context(domain, problem, ExecutionContext(1)).search_context
    state = search_context.state_repository.get_initial_state()

    assert evaluate_features(state, collect_features(program))["reachable-count"] == 2


def test_execute_empty_module_program_on_initial_goal_does_not_emit_open_state(tmp_path):
    from pyrunir_mcp.kr.ps.ext.execute.service import ExecutePolicyOptions, execute_policy

    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem = tmp_path / "p.pddl"
    problem.write_text("""(define (problem p)
  (:domain tiny)
  (:objects a b)
  (:init (at a))
  (:goal (at a)))
""", encoding="utf-8")
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

    assert result.is_successful
    assert not (out / "failures" / "open_state-001").exists()
    assert '"status": "SUCCESS"' in (out / "manifest.json").read_text(encoding="utf-8")
