"""End-to-end prove heuristic-column switches for base and ext policies."""

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


def _first_failure_doc(out, name: str):
    matches = sorted(out.glob(f"failures/*/{name}.psv"))
    assert matches, f"expected {name}.psv under {out}/failures"
    return matches[0].read_text(encoding="utf-8")


def test_base_prove_can_disable_hstar_independently(tmp_path):
    from pyrunir_mcp.kr.ps.base.schemas import ProvePolicyOptions
    from pyrunir_mcp.kr.ps.base.service import prove_policy

    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem = tmp_path / "p.pddl"
    problem.write_text(PROBLEM, encoding="utf-8")
    sketch = tmp_path / "sketch.txt"
    sketch.write_text(EMPTY_SKETCH, encoding="utf-8")

    lmcut_only = tmp_path / "lmcut-only"
    prove_policy(
        ProvePolicyOptions(
            domain_file=str(domain),
            problem_file=str(problem),
            sketch_file=str(sketch),
            output_dir=str(lmcut_only),
            include_hstar=False,
            include_hlmcut=True,
        )
    )
    text = _first_failure_doc(lmcut_only, "successors")
    assert "[states]\nid|flags|hlmcut" in text
    assert "hstar" not in text

    no_heuristics = tmp_path / "no-heuristics"
    prove_policy(
        ProvePolicyOptions(
            domain_file=str(domain),
            problem_file=str(problem),
            sketch_file=str(sketch),
            output_dir=str(no_heuristics),
            include_hstar=False,
            include_hlmcut=False,
        )
    )
    text = _first_failure_doc(no_heuristics, "successors")
    assert "hstar" not in text
    assert "hlmcut" not in text


def test_ext_prove_can_disable_hlmcut_independently(tmp_path):
    from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
    from pyrunir_mcp.kr.ps.ext.service import prove_module_program

    domain = tmp_path / "domain.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem = tmp_path / "p.pddl"
    problem.write_text(PROBLEM, encoding="utf-8")
    program = tmp_path / "program.txt"
    program.write_text(EMPTY_PROGRAM, encoding="utf-8")

    hstar_only = tmp_path / "hstar-only"
    prove_module_program(
        ProveModuleProgramOptions(
            domain_file=str(domain),
            problem_file=str(problem),
            module_program_file=str(program),
            output_dir=str(hstar_only),
            include_hstar=True,
            include_hlmcut=False,
        )
    )
    text = _first_failure_doc(hstar_only, "successors")
    assert "[states]\nid|flags|hstar" in text
    assert "hlmcut" not in text

    no_heuristics = tmp_path / "no-heuristics"
    prove_module_program(
        ProveModuleProgramOptions(
            domain_file=str(domain),
            problem_file=str(problem),
            module_program_file=str(program),
            output_dir=str(no_heuristics),
            include_hstar=False,
            include_hlmcut=False,
        )
    )
    text = _first_failure_doc(no_heuristics, "successors")
    assert "hstar" not in text
    assert "hlmcut" not in text
