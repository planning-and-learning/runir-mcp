import json
from pathlib import Path
from typing import NoReturn

import pytest

from pyrunir_mcp import (
    DumpFormat,
    FindModuleProgramSolutionResult,
    FindPolicySolutionResult,
    create_classifier,
    create_domain_context,
    create_module_program,
    create_policy,
    create_task_context,
    dump_result,
    find_solution,
)
from pyrunir_mcp.defaults import EXECUTE_SEARCH_BUDGET, PROVE_SEARCH_BUDGET
from pyrunir_mcp.keys import Keys
from pyrunir_mcp.kr.ps.proof import edge_summary, state_summary


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    domain_file = tmp_path / "domain.pddl"
    problem_file = tmp_path / "problem.pddl"
    classifier_file = tmp_path / "classifier.txt"
    domain_file.write_text(
        """(define (domain tiny-find-solution)
  (:requirements :strips :typing)
  (:constants marker)
  (:predicates (p) (q))
  (:action make-q :parameters () :precondition (p) :effect (q))
  (:action trap :parameters () :precondition (p) :effect (not (p))))
""",
        encoding="utf-8",
    )
    problem_file.write_text(
        """(define (problem tiny-find-solution-p)
  (:domain tiny-find-solution)
  (:init (p))
  (:goal (q)))
""",
        encoding="utf-8",
    )
    classifier_file.write_text(
        """(:classifier
    (:symbol c0)
    (:features
        (:boolean
            (:symbol any_object)
            (:expression (b_nonempty (c_top)))
        )
    )
    (:expression (or (and any_object)))
)
""",
        encoding="utf-8",
    )
    return domain_file, problem_file, classifier_file


def _assert_classifier_terminal(result: FindPolicySolutionResult | FindModuleProgramSolutionResult) -> None:
    proof = result.results[0][1]
    assert proof.graph is not None
    assert proof.deadend_states
    label = proof.graph.get_vertex_property(int(proof.deadend_states[0]))
    assert label.is_unsolvable


def _assert_hstar_requires_evidence(
    result: FindPolicySolutionResult | FindModuleProgramSolutionResult,
) -> None:
    graph = result.results[0][1].graph
    vertex = int(next(graph.get_vertex_indices()))
    assert Keys.HSTAR not in state_summary(graph, vertex)
    assert state_summary(graph, vertex, lambda _state: {Keys.HSTAR: 7})[Keys.HSTAR] == 7


def test_find_solution_dispatch_modes_seeds_and_classifier(tmp_path: Path) -> None:
    domain_file, problem_file, classifier_file = _inputs(tmp_path)
    domain = create_domain_context(domain_file)
    task = create_task_context(domain, problem_file)
    policy = create_policy(domain, None)
    program = create_module_program(domain, None)
    classifier = create_classifier(domain, classifier_file)

    policy_result = find_solution(task, policy, num_rollouts=3, random_seed_start=20)
    assert isinstance(policy_result, FindPolicySolutionResult)
    assert policy_result.candidate is policy
    assert [seed for seed, _ in policy_result.results] == [20, 21, 22]
    assert policy_result.search_budget == EXECUTE_SEARCH_BUDGET
    _assert_hstar_requires_evidence(policy_result)

    single_result = find_solution(task, policy, random_seed=9, random_seed_start=100)
    assert [seed for seed, _ in single_result.results] == [9]

    program_result = find_solution(task, program, num_rollouts=2, random_seed_start=30)
    assert isinstance(program_result, FindModuleProgramSolutionResult)
    assert program_result.candidate is program
    assert [seed for seed, _ in program_result.results] == [30, 31]
    _assert_hstar_requires_evidence(program_result)

    universal_result = find_solution(
        task,
        policy,
        universal=True,
        num_rollouts=4,
        random_seed=7,
        random_seed_start=100,
    )
    assert [seed for seed, _ in universal_result.results] == [7]
    assert universal_result.search_budget == PROVE_SEARCH_BUDGET

    policy_classified = find_solution(task, policy, classifier=classifier)
    program_classified = find_solution(task, program, classifier=classifier)
    assert policy_classified.candidate is policy
    assert policy_classified.classifier is classifier
    assert program_classified.candidate is program
    assert program_classified.classifier is classifier
    _assert_classifier_terminal(policy_classified)
    _assert_classifier_terminal(program_classified)

    planning_domain = domain.planning_domain
    assert task.base_task.get_policy(planning_domain, policy) is task.base_task.get_policy(
        planning_domain, policy
    )
    assert task.ext_task.get_module_program(
        planning_domain, program
    ) is task.ext_task.get_module_program(planning_domain, program)
    assert task.base_task.get_classifier(
        planning_domain, classifier
    ) is task.base_task.get_classifier(planning_domain, classifier)

    second_task = create_task_context(domain, problem_file)
    assert second_task.base_task.get_policy(
        planning_domain, policy
    ) is not task.base_task.get_policy(planning_domain, policy)
    assert second_task.ext_task.get_module_program(
        planning_domain, program
    ) is not task.ext_task.get_module_program(planning_domain, program)
    assert second_task.base_task.get_classifier(
        planning_domain, classifier
    ) is not task.base_task.get_classifier(planning_domain, classifier)

    with pytest.raises(ValueError, match="num_rollouts must be at least 1"):
        find_solution(task, policy, num_rollouts=0)


def test_ext_solution_edges_report_actions(tmp_path: Path) -> None:
    domain_file, problem_file, _ = _inputs(tmp_path)
    program_file = tmp_path / "program.txt"
    program_file.write_text(
        """(:program
    (:entry solve)
    (:module
        (:symbol solve)
        (:arguments)
        (:registers)
        (:entry m0)
        (:memory m0 m1)
        (:features)
        (:rules
            (:rule
                (:symbol solve)
                (:expression
                    (:source-memory m0)
                    (:target-memory m1)
                    (:do
                        (:conditions)
                        (:action "make-q")
                        (:arguments)
                        (:effects)
                    )
                )
            )
        )
    )
)
""",
        encoding="utf-8",
    )
    domain = create_domain_context(domain_file)
    task = create_task_context(domain, problem_file)
    program = create_module_program(domain, program_file)

    result = find_solution(task, program)
    proof = result.results[0][1]
    assert proof.graph is not None
    actions = [
        edge_summary(proof.graph, int(edge)).get(Keys.ACTION)
        for edge in proof.graph.get_edge_indices()
    ]
    assert "make-q()" in actions


def test_universal_dump_fills_unused_failure_capacity_with_successes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    domain_file, problem_file, _ = _inputs(tmp_path)
    policy_file = tmp_path / "policy.txt"
    policy_file.write_text(
        """(:sketch
    (:features)
    (:rules
        (:rule
            (:symbol any-transition)
            (:expression (:conditions) (:effects))
        )
    )
)
""",
        encoding="utf-8",
    )
    domain = create_domain_context(domain_file)
    task = create_task_context(domain, problem_file)
    policy = create_policy(domain, policy_file)

    result = find_solution(task, policy, universal=True, num_rollouts=3)
    dumped = dump_result(
        result,
        tmp_path / "solution",
        formats=(DumpFormat.PSV, DumpFormat.JSON),
    )
    manifest = json.loads(
        (dumped.output_dir / "manifest.json").read_text(encoding="utf-8")
    )

    assert result.status.value == "failure"
    assert len(manifest["failures"]) == 1
    assert len(manifest["successes"]) == 1
    assert manifest["failures"][0]["seed"] is None
    assert manifest["successes"][0]["seed"] is None
    assert (dumped.output_dir / "successes" / "success-001" / "witness_trace.psv").is_file()
    assert "@tool runir.ps.find_solution" in (
        dumped.output_dir / "successes" / "success-001" / "witness_trace.psv"
    ).read_text(encoding="utf-8")

    import pyrunir_mcp.dumping as dumping

    def unexpected(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("successful witness traces must not be constructed")

    monkeypatch.setattr(dumping, "successful_witness_trace_artifacts", unexpected)
    without_witness_traces = dump_result(
        result,
        tmp_path / "solution_without_witness_traces",
        formats=(DumpFormat.PSV,),
        include_witness_trace=False,
    )
    without_manifest = json.loads(
        (without_witness_traces.output_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert without_manifest["successes"] == []
    assert without_manifest["evidence"]["witness_trace"] is False
    assert not (without_witness_traces.output_dir / "successes").exists()


@pytest.mark.parametrize(
    ("include_witness_trace", "include_plan_trace", "include_successors"),
    [
        (False, False, False),
        (False, False, True),
        (False, True, False),
        (False, True, True),
        (True, False, False),
        (True, False, True),
        (True, True, False),
        (True, True, True),
    ],
)
def test_dump_solution_evidence_options_are_independent(
    tmp_path: Path,
    include_witness_trace: bool,
    include_plan_trace: bool,
    include_successors: bool,
) -> None:
    domain_file, problem_file, _ = _inputs(tmp_path)
    domain = create_domain_context(domain_file)
    task = create_task_context(domain, problem_file)
    policy = create_policy(domain, None)
    result = find_solution(task, policy)

    dumped = dump_result(
        result,
        tmp_path / "solution",
        formats=(DumpFormat.PSV,),
        include_witness_trace=include_witness_trace,
        include_plan_trace=include_plan_trace,
        include_successors=include_successors,
    )
    manifest = json.loads(
        (dumped.output_dir / "manifest.json").read_text(encoding="utf-8")
    )
    failure = manifest["failures"][0]
    failure_dir = dumped.output_dir / "failures" / "open_state-001"

    assert manifest["schema_version"] == 2
    assert manifest["evidence"] == {
        "witness_trace": include_witness_trace,
        "plan_trace": include_plan_trace,
        "successors": include_successors,
    }
    assert (failure_dir / "witness.psv").is_file()
    assert (failure["witness_trace_path"] is not None) is include_witness_trace
    assert (failure["plan_trace_path"] is not None) is include_plan_trace
    assert (failure["successors_path"] is not None) is include_successors
    assert (failure_dir / "witness_trace.psv").exists() is include_witness_trace
    assert (failure_dir / "plan_trace.psv").exists() is include_plan_trace
    assert (failure_dir / "successors.psv").exists() is include_successors
    assert not (failure_dir / "trace.psv").exists()
    assert "trace_path" not in failure


def test_disabled_solution_evidence_skips_expensive_builders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyrunir_mcp.dumping as dumping
    import pyrunir_mcp.kr.ps.proof as proof

    domain_file, problem_file, _ = _inputs(tmp_path)
    domain = create_domain_context(domain_file)
    task = create_task_context(domain, problem_file)
    result = find_solution(task, create_policy(domain, None))

    def unexpected(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("disabled evidence builder was called")

    monkeypatch.setattr(dumping, "make_frontier_expander", unexpected)
    monkeypatch.setattr(dumping, "plan_open_state_trace", unexpected)
    monkeypatch.setattr(proof, "_witness_trace_document", unexpected)

    dumped = dump_result(
        result,
        tmp_path / "solution",
        formats=(DumpFormat.PSV,),
        include_witness_trace=False,
        include_plan_trace=False,
        include_successors=False,
    )
    assert (dumped.output_dir / "failures" / "open_state-001" / "witness.psv").is_file()
