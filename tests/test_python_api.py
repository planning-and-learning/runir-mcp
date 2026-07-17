from __future__ import annotations

import json
from pathlib import Path
from typing import NoReturn, cast

import pytest
from pyrunir.kr.ps.base import Sketch
from pytyr.planning import SearchStatus

import pyrunir_mcp as public
from pyrunir_mcp import (
    CandidateSource,
    ClassifierObservationDetails,
    ClassifierProofCounts,
    DumpFormat,
    FailureFingerprint,
    FindPolicySolutionResult,
    FindSolutionObservationDetails,
    IncompleteTerminationStatus,
    Policy,
    PolicyTerminationObservationDetails,
    ProvePolicyTerminationResult,
    ProveTerminationResult,
    SearchBudget,
    TaskContext,
    ValidationHistory,
    ValidationKind,
    ValidationObservation,
    ValidationStatus,
    create_domain_context,
    create_module_program,
    create_task_context,
    dump_result,
    dump_validation_history,
    find_solution,
    get_generator_domain_path,
    prove_termination,
)
from pyrunir_mcp.dumping import solution_observation_from_manifest
from pyrunir_mcp.validation import (
    TerminationObservationDetails,
    rotate_smallest_state_id_first,
)


def test_public_exports_use_typed_names() -> None:
    assert public.Policy is Policy
    assert public.FindSolutionObservationDetails is FindSolutionObservationDetails
    assert public.ClassifierObservationDetails is ClassifierObservationDetails
    assert public.IncompleteTerminationStatus is IncompleteTerminationStatus
    assert public.PolicyTerminationObservationDetails is PolicyTerminationObservationDetails
    assert public.ProvePolicyTerminationResult is ProvePolicyTerminationResult
    assert public.prove_termination is prove_termination
    assert not hasattr(public, "prove_policy_termination")


def _failed_solution_details(num_rollouts: int = 1) -> FindSolutionObservationDetails:
    return FindSolutionObservationDetails(
        proof_statuses=(),
        successful=False,
        universal=False,
        num_rollouts=num_rollouts,
    )


def test_task_context_reuses_ground_semantic_resources(tmp_path: Path) -> None:
    domain_file = tmp_path / "domain.pddl"
    problem_file = tmp_path / "problem.pddl"
    domain_file.write_text(
        "(define (domain tiny-context) (:requirements :strips) (:predicates (p)))",
        encoding="utf-8",
    )
    problem_file.write_text(
        "(define (problem tiny-context-p) (:domain tiny-context) (:init (p)) (:goal (p)))",
        encoding="utf-8",
    )

    domain = create_domain_context(domain_file)
    first = create_task_context(domain, problem_file)
    second = create_task_context(domain, problem_file)
    first_loaded = first.base_task
    second_loaded = second.base_task
    first_ground = first_loaded.search_context

    assert first_loaded is first.ext_task
    assert first_ground is first_loaded.task_context.search_context
    assert first_loaded.task_context is not second_loaded.task_context
    assert first_loaded.task_context.base_repository is first_loaded.task_context.base_repository
    assert first_loaded.task_context.ext_repository is first_loaded.task_context.ext_repository
    assert first_loaded.task_context.uns_repository is first_loaded.task_context.uns_repository
    assert (
        first_loaded.task_context.base_repository is not second_loaded.task_context.base_repository
    )
    assert first_loaded.task_context.ext_repository is not second_loaded.task_context.ext_repository
    assert first_loaded.task_context.uns_repository is not second_loaded.task_context.uns_repository
    assert first_loaded.task_context.dl_builder is not second_loaded.task_context.dl_builder
    assert (
        first_loaded.task_context.dl_denotation_repository
        is not second_loaded.task_context.dl_denotation_repository
    )
    assert not hasattr(first_ground, "dl_builder")
    assert not hasattr(first_ground, "dl_denotation_repository")


def test_cycle_fingerprint_rotates_smallest_state_id_first() -> None:
    assert rotate_smallest_state_id_first(["s3384", "s3403", "s3384"]) == (
        "s3384",
        "s3403",
        "s3384",
    )
    assert rotate_smallest_state_id_first(["s42", "s7", "s11"]) == (
        "s7",
        "s11",
        "s42",
    )


def test_ext_cycle_fingerprint_rotates_by_module_memory_state_triple() -> None:
    assert rotate_smallest_state_id_first(["M1|m0|s1", "M0|m2|s0", "M0|m1|s2", "M1|m0|s1"]) == (
        "M0|m1|s2",
        "M1|m0|s1",
        "M0|m2|s0",
        "M0|m1|s2",
    )


def test_empty_classifier_dumps_false_negative_witness_artifacts(tmp_path: Path) -> None:
    domain_file = tmp_path / "domain.pddl"
    problem_file = tmp_path / "problem.pddl"
    domain_file.write_text(
        "\n".join(
            [
                "(define (domain tiny-uns)",
                "  (:requirements :strips :typing :negative-preconditions)",
                "  (:predicates (p) (q) (dead))",
                "  (:action solve :parameters () :precondition (p) :effect (q))",
                "  (:action trap :parameters () :precondition (p) :effect (and (dead) (not (p))))",
                ")",
            ]
        ),
        encoding="utf-8",
    )
    problem_file.write_text(
        "\n".join(
            [
                "(define (problem tiny-uns-p)",
                "  (:domain tiny-uns)",
                "  (:init (p))",
                "  (:goal (q))",
                ")",
            ]
        ),
        encoding="utf-8",
    )

    domain = create_domain_context(domain_file)
    task = create_task_context(domain, problem_file)
    classifier = public.create_classifier(domain, None)

    result = public.prove_classifier(
        task,
        classifier,
        search_budget=SearchBudget(max_num_states=100, max_time_seconds=5.0),
    )
    dumped = dump_result(result, tmp_path / "uns_prove", formats=(DumpFormat.PSV, DumpFormat.JSON))

    output_dir = dumped.output_dir
    witness = output_dir / "failures" / "false_negative-001" / "witness.psv"
    atoms = output_dir / "dicts" / "atoms.psv"

    assert result.status.value == "failure"
    assert result.counts.false_negative == 1
    assert (output_dir / "run.json").is_file()
    assert json.loads((output_dir / "run.json").read_text(encoding="utf-8"))["evidence"] == {
        "classifier_witness": True
    }
    assert (output_dir / "summary.psv").is_file()
    assert witness.is_file()
    assert atoms.is_file()
    assert "[states]" in witness.read_text(encoding="utf-8")
    assert "[facts]" in witness.read_text(encoding="utf-8")
    assert "p0|fluent_atoms|" in atoms.read_text(encoding="utf-8")

    without_witnesses = dump_result(
        result,
        tmp_path / "uns_prove_without_witnesses",
        formats=(DumpFormat.PSV,),
        include_witness=False,
    )
    without_output_dir = without_witnesses.output_dir
    without_run = json.loads((without_output_dir / "run.json").read_text(encoding="utf-8"))
    without_result = json.loads((without_output_dir / "result.json").read_text(encoding="utf-8"))
    assert without_run["evidence"] == {"classifier_witness": False}
    assert without_run["counterexamples"][0]["category"] == "false_negative"
    assert without_run["counterexamples"][0]["witness_path"] is None
    assert without_run["metadata"]["counts"]["false_negative_count"] == 1
    assert (
        without_result["observation"]
        == json.loads((output_dir / "result.json").read_text(encoding="utf-8"))["observation"]
    )
    assert not (without_output_dir / "failures").exists()
    assert not (without_output_dir / "dicts").exists()


def test_empty_module_program_find_solution_dumps_open_state_artifacts(
    tmp_path: Path,
) -> None:
    domain_file = tmp_path / "domain.pddl"
    problem_file = tmp_path / "problem.pddl"
    classifier_file = tmp_path / "classifier.txt"
    domain_file.write_text(
        "\n".join(
            [
                "(define (domain tiny-open)",
                "  (:requirements :strips :typing)",
                "  (:constants marker)",
                "  (:predicates (p) (q))",
                "  (:action make-q :parameters () :precondition (p) :effect (q))",
                ")",
            ]
        ),
        encoding="utf-8",
    )
    problem_file.write_text(
        "\n".join(
            [
                "(define (problem tiny-open-p)",
                "  (:domain tiny-open)",
                "  (:init (p))",
                "  (:goal (q))",
                ")",
            ]
        ),
        encoding="utf-8",
    )

    domain = create_domain_context(domain_file)
    task = create_task_context(domain, problem_file)
    program = create_module_program(domain, None)

    result = find_solution(
        task,
        program,
        num_rollouts=1,
        random_seed_start=0,
        search_budget=SearchBudget(max_num_states=200, max_time_seconds=5.0),
        plan_trace_budget=SearchBudget(max_num_states=10_000, max_time_seconds=5.0),
    )
    dumped = dump_result(
        result,
        tmp_path / "ext_find_solution",
        formats=(DumpFormat.PSV, DumpFormat.JSON),
    )

    output_dir = dumped.output_dir
    witness = output_dir / "failures" / "open_state-001" / "witness.psv"
    witness_trace = output_dir / "failures" / "open_state-001" / "witness_trace.psv"
    successors = output_dir / "failures" / "open_state-001" / "successors.psv"

    assert result.status.value == "failure"
    assert witness.is_file()
    assert witness_trace.is_file()
    assert successors.is_file()
    witness_text = witness.read_text(encoding="utf-8")
    assert "@category open_state" in witness_text
    assert "[states]" in witness_text
    assert "[transitions]" in witness_trace.read_text(encoding="utf-8")

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
    classifier = public.create_classifier(domain, classifier_file)
    classified = find_solution(task, program, classifier=classifier)
    classified_dump = dump_result(
        classified,
        tmp_path / "ext_find_solution_classified",
        formats=(DumpFormat.PSV,),
    )
    classified_witness = classified_dump.output_dir / "failures" / "deadend-001" / "witness.psv"

    classified_proof = classified.results[0][1]
    classified_label = classified_proof.graph.get_vertex_property(
        classified_proof.deadend_states[0]
    )
    assert classified_label.is_unsolvable
    assert classified_witness.is_file()
    assert "witness,deadend" in classified_witness.read_text(encoding="utf-8")
    assert not (classified_dump.output_dir / "failures" / "deadend-001" / "successors.psv").exists()


def _assert_policy_incomplete_termination_status(
    result: ProvePolicyTerminationResult,
    output_dir: Path,
    expected: IncompleteTerminationStatus,
) -> None:
    details = result.observation.details
    assert isinstance(details, PolicyTerminationObservationDetails)
    assert result.incomplete_termination_status is expected
    assert details.incomplete_termination_status is expected

    result_json = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    run_json = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    assert result_json["termination"]["incomplete_termination_status"] == expected.value
    assert result_json["observation"]["details"]["incomplete_termination_status"] == expected.value
    assert run_json["metadata"]["incomplete_termination_status"] == expected.value
    assert run_json["primary"]["incomplete_termination_status"] == expected.value


def test_empty_policy_termination_dumps_run_artifacts(tmp_path: Path) -> None:
    domain_file = tmp_path / "domain.pddl"
    domain_file.write_text(
        "(define (domain tiny-policy-term) (:requirements :strips) (:predicates (p)))",
        encoding="utf-8",
    )
    domain = create_domain_context(domain_file)
    policy = public.create_policy(domain, None)

    result = prove_termination(domain, policy)
    dumped = dump_result(
        result,
        tmp_path / "base_termination",
        formats=(DumpFormat.PSV, DumpFormat.JSON),
    )

    output_dir = dumped.output_dir
    run_json = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    assert result.status is ValidationStatus.SUCCESS
    assert result.policy_result.scc_results is None
    complete_result = prove_termination(
        domain,
        policy,
        use_incomplete_preprocessing=False,
    )
    assert complete_result.policy_result.scc_results == []
    _assert_policy_incomplete_termination_status(
        result,
        output_dir,
        IncompleteTerminationStatus.PROVED,
    )
    assert run_json["tool"] == "runir.ps.base.prove_termination"
    assert (output_dir / "summary.psv").is_file()
    assert (output_dir / "dicts" / "variables.psv").is_file()
    assert not (output_dir / "dicts" / "memory.psv").exists()


def test_nonterminating_policy_dumps_native_graph_witness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = create_domain_context(get_generator_domain_path("gripper"))
    policy_file = tmp_path / "policy.txt"
    policy_file.write_text(
        """(:sketch
    (:features
        (:boolean
            (:symbol b1)
            (:expression (b_nonempty (c_atomic_state "at-robby")))
        )
    )
    (:rules
        (:rule
            (:symbol auto1)
            (:expression
                (:conditions (negative b1))
                (:effects (positive b1))
            )
        )
        (:rule
            (:symbol auto2)
            (:expression
                (:conditions (positive b1))
                (:effects (negative b1))
            )
        )
    )
)
""",
        encoding="utf-8",
    )
    policy = public.create_policy(domain, policy_file)

    insufficient_result = prove_termination(domain, policy, max_features=1)
    insufficient_dump = dump_result(
        insufficient_result,
        tmp_path / "base_termination_insufficient",
        formats=(DumpFormat.JSON,),
    )
    _assert_policy_incomplete_termination_status(
        insufficient_result,
        insufficient_dump.output_dir,
        IncompleteTerminationStatus.INSUFFICIENT,
    )

    result = prove_termination(
        domain,
        policy,
        max_features=1,
        use_incomplete_preprocessing=False,
    )
    dumped = dump_result(
        result,
        tmp_path / "base_termination_failure",
        formats=(DumpFormat.PSV, DumpFormat.JSON),
    )

    run_json = json.loads((dumped.output_dir / "run.json").read_text(encoding="utf-8"))
    witness = dumped.output_dir / "failures" / "structural_termination-001" / "witness.psv"
    assert result.status is ValidationStatus.FAILURE
    _assert_policy_incomplete_termination_status(
        result,
        dumped.output_dir,
        IncompleteTerminationStatus.DISABLED,
    )
    assert result.observation.fingerprint is not None
    assert result.observation.fingerprint.witness == ("non_terminating",)
    assert run_json["status"] == "failure"
    assert run_json["metadata"]["program_status"] == "non_terminating"
    assert witness.is_file()
    witness_text = witness.read_text(encoding="utf-8")
    assert "[vertices]" in witness_text
    assert "[edges]" in witness_text
    assert "memory_id" not in witness_text
    assert "b1" in (dumped.output_dir / "dicts" / "variables.psv").read_text(encoding="utf-8")
    assert not (dumped.output_dir / "dicts" / "memory.psv").exists()

    import pyrunir_mcp.dumping as dumping

    def unexpected(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("termination witness builder was called")

    monkeypatch.setattr(dumping, "_policy_termination_vertices_edges", unexpected)
    without_witness = dump_result(
        result,
        tmp_path / "base_termination_without_witness",
        formats=(DumpFormat.PSV,),
        include_witness=False,
    )
    without_run = json.loads((without_witness.output_dir / "run.json").read_text(encoding="utf-8"))
    assert without_run["evidence"] == {"termination_witness": False}
    assert without_run["counterexamples"][0]["witness_path"] is None
    assert without_run["status"] == "failure"
    assert "structural_termination-001" in (without_witness.output_dir / "summary.psv").read_text(
        encoding="utf-8"
    )
    assert not (without_witness.output_dir / "failures").exists()
    assert result.observation.fingerprint is not None
    without_result = json.loads(
        (without_witness.output_dir / "result.json").read_text(encoding="utf-8")
    )
    assert without_result["observation"]["witness"] == list(result.observation.fingerprint.witness)


def _assert_incomplete_termination_status(
    result: ProveTerminationResult,
    output_dir: Path,
    expected: IncompleteTerminationStatus,
) -> None:
    details = result.observation.details
    assert isinstance(details, TerminationObservationDetails)
    assert result.incomplete_termination_status is expected
    assert details.incomplete_termination_status is expected

    result_json = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    run_json = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    assert result_json["termination"]["incomplete_termination_status"] == expected.value
    assert result_json["observation"]["details"]["incomplete_termination_status"] == expected.value
    assert run_json["metadata"]["incomplete_termination_status"] == expected.value
    assert run_json["primary"]["incomplete_termination_status"] == expected.value


def test_empty_module_program_termination_dumps_run_artifacts(tmp_path: Path) -> None:
    domain_file = tmp_path / "domain.pddl"
    domain_file.write_text(
        "\n".join(
            [
                "(define (domain tiny-term)",
                "  (:requirements :strips :typing)",
                "  (:predicates (p))",
                "  (:action noop :parameters () :precondition (p) :effect (p))",
                ")",
            ]
        ),
        encoding="utf-8",
    )

    domain = create_domain_context(domain_file)
    program = create_module_program(domain, None)

    result = prove_termination(domain, program)
    dumped = dump_result(
        result, tmp_path / "ext_termination", formats=(DumpFormat.PSV, DumpFormat.JSON)
    )

    output_dir = dumped.output_dir
    assert (output_dir / "result.json").is_file()
    run_json = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))

    assert result.status.value == "success"
    assert all(
        module_result.scc_results is None for module_result in result.program_result.module_results
    )
    complete_result = prove_termination(
        domain,
        program,
        use_incomplete_preprocessing=False,
    )
    assert all(
        module_result.scc_results == []
        for module_result in complete_result.program_result.module_results
    )
    _assert_incomplete_termination_status(
        result,
        output_dir,
        IncompleteTerminationStatus.PROVED,
    )
    assert run_json["tool"] == "runir.ps.ext.prove_termination"
    assert (output_dir / "summary.psv").is_file()
    assert (output_dir / "dicts" / "variables.psv").is_file()


def test_nonterminating_module_program_dumps_native_graph_witness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    domain = create_domain_context(get_generator_domain_path("gripper"))
    program_file = tmp_path / "program.txt"
    program_file.write_text(
        """(:program
    (:entry nonterm)
    (:module
        (:symbol nonterm)
        (:arguments)
        (:registers)
        (:entry m0)
        (:memory m0 m1)
        (:features
            (:numerical
                (:symbol fn)
                (:expression (n_count (c_atomic_state \"ball\")))
            )
        )
        (:rules
            (:rule
                (:symbol loop1)
                (:expression
                    (:source-memory m0)
                    (:target-memory m1)
                    (:sketch (:conditions) (:effects (unchanged fn)))
                )
            )
            (:rule
                (:symbol loop2)
                (:expression
                    (:source-memory m1)
                    (:target-memory m0)
                    (:sketch (:conditions) (:effects (unchanged fn)))
                )
            )
        )
    )
)\n""",
        encoding="utf-8",
    )
    program = create_module_program(domain, program_file)

    insufficient_result = prove_termination(domain, program, max_features=1)
    insufficient_dump = dump_result(
        insufficient_result,
        tmp_path / "termination_insufficient",
        formats=(DumpFormat.JSON,),
    )
    _assert_incomplete_termination_status(
        insufficient_result,
        insufficient_dump.output_dir,
        IncompleteTerminationStatus.INSUFFICIENT,
    )

    result = prove_termination(
        domain,
        program,
        max_features=1,
        use_incomplete_preprocessing=False,
    )
    dumped = dump_result(
        result,
        tmp_path / "termination_failure",
        formats=(DumpFormat.PSV, DumpFormat.JSON),
    )

    run_json = json.loads((dumped.output_dir / "run.json").read_text(encoding="utf-8"))
    witness = dumped.output_dir / "failures" / "structural_termination-001" / "witness.psv"
    assert result.status is ValidationStatus.FAILURE
    _assert_incomplete_termination_status(
        result,
        dumped.output_dir,
        IncompleteTerminationStatus.DISABLED,
    )
    assert result.nonterminating_modules == ("nonterm",)
    assert result.observation.fingerprint is not None
    assert result.observation.fingerprint.witness == ("non_terminating", "nonterm")
    assert run_json["status"] == "failure"
    assert run_json["metadata"]["program_status"] == "non_terminating"
    assert witness.is_file()
    witness_text = witness.read_text(encoding="utf-8")
    assert "[vertices]" in witness_text
    assert "[edges]" in witness_text
    assert "fn" in (dumped.output_dir / "dicts" / "variables.psv").read_text(encoding="utf-8")

    import pyrunir_mcp.dumping as dumping

    def unexpected(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("termination witness builder was called")

    monkeypatch.setattr(dumping, "_termination_vertices_edges", unexpected)
    without_witness = dump_result(
        result,
        tmp_path / "termination_without_witness",
        formats=(DumpFormat.PSV,),
        include_witness=False,
    )
    without_run = json.loads((without_witness.output_dir / "run.json").read_text(encoding="utf-8"))
    assert without_run["evidence"] == {"termination_witness": False}
    assert without_run["counterexamples"][0]["witness_path"] is None
    assert without_run["status"] == "failure"
    assert "structural_termination-001" in (without_witness.output_dir / "summary.psv").read_text(
        encoding="utf-8"
    )
    assert not (without_witness.output_dir / "failures").exists()
    assert result.observation.fingerprint is not None
    without_result = json.loads(
        (without_witness.output_dir / "result.json").read_text(encoding="utf-8")
    )
    assert without_result["observation"]["witness"] == list(result.observation.fingerprint.witness)


def test_solution_fingerprint_refresh_promotes_cycle_witness(tmp_path: Path) -> None:
    witness_path = tmp_path / "cycle_witness.psv"
    witness_path.write_text(
        """@tool runir.ps.find_solution
@id open_state-001
@category cycle

[states]
state_id|flags
s8666|open,witness,cycle
s8698|
s8793|
s8697|
s8666|open,witness,cycle
""",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "failures": [
                    {
                        "category": "cycle",
                        "task_file": "p03.pddl",
                        "witness_path": witness_path.as_posix(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=FindSolutionObservationDetails(
            proof_statuses=(),
            successful=False,
            universal=False,
            num_rollouts=1,
        ),
        fingerprint=None,
    )
    result = FindPolicySolutionResult(
        id="result_000001",
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        context=cast(TaskContext, None),
        candidate=cast(Policy, None),
        observation=observation,
        classifier=None,
        universal=False,
        num_rollouts=1,
        results=(),
        search_budget=SearchBudget(None, None),
        plan_trace_budget=SearchBudget(1_000_000, 10.0),
    )

    refreshed = solution_observation_from_manifest(result, manifest_path)

    assert result.observation.fingerprint is None
    assert refreshed.fingerprint == FailureFingerprint(
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        problem_file="p03.pddl",
        category="cycle",
        witness=("s8666", "s8698", "s8793", "s8697", "s8666"),
    )


def test_solution_fingerprint_refresh_uses_manifest_witness(tmp_path: Path) -> None:
    witness_path = tmp_path / "witness.psv"
    witness_path.write_text(
        """@tool runir.ps.find_solution
@id deadend-001
@category deadend

[states]
state_id|flags|f0
s339|witness,deadend|2

[facts]
state_id|atom_ids
s339|p0
""",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "failures": [
                    {
                        "category": "deadend",
                        "task_file": "p01.pddl",
                        "witness_path": witness_path.as_posix(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    original = FailureFingerprint(
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        problem_file="p01.pddl",
        category="open_state",
        witness=("s0",),
    )
    observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=FindSolutionObservationDetails(
            proof_statuses=(),
            successful=False,
            universal=False,
            num_rollouts=1,
        ),
        fingerprint=original,
    )
    result = FindPolicySolutionResult(
        id="result_000001",
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        context=cast(TaskContext, None),
        candidate=cast(Policy, None),
        observation=observation,
        classifier=None,
        universal=False,
        num_rollouts=1,
        results=(),
        search_budget=SearchBudget(None, None),
        plan_trace_budget=SearchBudget(1_000_000, 10.0),
    )

    refreshed = solution_observation_from_manifest(result, manifest_path)

    assert result.observation.fingerprint == original
    assert refreshed.fingerprint == FailureFingerprint(
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        problem_file="p01.pddl",
        category="deadend",
        witness=("s339",),
    )


def test_dump_result_reports_reserved_rich_output_dir(tmp_path: Path) -> None:
    domain_file = tmp_path / "domain.pddl"
    domain_file.write_text(
        """(define (domain seq)
  (:requirements :strips)
  (:predicates (a))
  (:action setA :parameters () :precondition () :effect (a)))
""",
        encoding="utf-8",
    )
    domain = create_domain_context(domain_file)
    program = create_module_program(domain, None)
    first = dump_result(
        prove_termination(domain, program), tmp_path / "termination", formats=(DumpFormat.PSV,)
    )
    second = dump_result(
        prove_termination(domain, program), tmp_path / "termination", formats=(DumpFormat.PSV,)
    )

    assert first.output_dir == (tmp_path / "termination").resolve()
    assert second.output_dir == (tmp_path / "termination" / "run-002").resolve()
    assert (second.output_dir / "run.json").is_file()
    assert (second.output_dir / "result.json").is_file()
    assert (second.output_dir / "summary.psv").is_file()


def test_validation_history_keeps_typed_observations_until_dump(tmp_path: Path) -> None:
    history = ValidationHistory()
    observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=_failed_solution_details(num_rollouts=3),
    )
    feedback = history.fold(observation)

    assert feedback.repeated is False
    assert feedback.previous_occurrences == 0
    assert isinstance(history.observations[0].details, FindSolutionObservationDetails)
    assert history.observations[0].details.num_rollouts == 3

    dumped = dump_validation_history(history, tmp_path / "history", formats=(DumpFormat.JSON,))
    assert dumped.files == (tmp_path / "history" / "history.json",)
    payload = json.loads(dumped.files[0].read_text(encoding="utf-8"))

    assert payload["observations"] == [
        {
            "result_id": "result_000001",
            "kind": "base_find_solution",
            "status": "failure",
            "candidate_id": "policy_000001",
            "classifier_id": None,
            "witness": None,
            "details": {
                "rollout_count": 3,
                "universal": False,
                "successful": False,
                "proof_statuses": [],
            },
        }
    ]


def test_history_fold_reports_repeated_observations() -> None:
    history = ValidationHistory()
    observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=_failed_solution_details(),
    )

    first = history.fold(observation)
    second = history.fold(observation)

    assert first.repeated is False
    assert second.repeated is True
    assert second.previous_occurrences == 1
    assert second.total_observations == 2


def test_history_fold_uses_failure_fingerprint_when_present() -> None:
    history = ValidationHistory()
    fingerprint = FailureFingerprint(
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        problem_file="p01.pddl",
        category="open_state",
        witness=("s7",),
    )
    first_observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=_failed_solution_details(),
        fingerprint=fingerprint,
    )
    second_observation = ValidationObservation(
        result_id="result_000002",
        kind=ValidationKind.BASE_FIND_SOLUTION,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000002",
        classifier_id=None,
        details=_failed_solution_details(),
        fingerprint=fingerprint,
    )

    first = history.fold(first_observation)
    second = history.fold(second_observation)

    assert first.repeated is False
    assert second.repeated is True
    assert second.previous_occurrences == 1


def test_classifier_observation_details_dump_with_enum_status(tmp_path: Path) -> None:
    history = ValidationHistory()
    history.fold(
        ValidationObservation(
            result_id="result_000002",
            kind=ValidationKind.UNS_PROVE,
            status=ValidationStatus.FAILURE,
            candidate_id="classifier_000001",
            classifier_id=None,
            details=ClassifierObservationDetails(
                counts=ClassifierProofCounts(
                    states=10,
                    unsolvable=4,
                    false_positive=1,
                    false_negative=2,
                ),
                state_graph_status=SearchStatus.OUT_OF_TIME,
            ),
        )
    )

    dumped = dump_validation_history(history, tmp_path / "history")
    payload = json.loads(dumped.files[0].read_text(encoding="utf-8"))

    assert payload["observations"][0]["witness"] is None
    assert payload["observations"][0]["details"] == {
        "counts": {
            "state_count": 10,
            "unsolvable_state_count": 4,
            "false_positive_count": 1,
            "false_negative_count": 2,
        },
        "state_graph_status": "out_of_time",
    }


def test_policy_candidate_source_uses_enum() -> None:
    policy = Policy(
        id="policy_000001",
        value=cast(Sketch, None),
        source=CandidateSource.EMPTY,
    )

    assert policy.source is CandidateSource.EMPTY


def test_write_empty_policy_uses_canonical_runir_text(tmp_path: Path) -> None:
    domain_path = tmp_path / "domain.pddl"
    domain_path.write_text(
        """(define (domain seq)
  (:requirements :strips)
  (:predicates (a))
  (:action setA :parameters () :precondition () :effect (a)))
""",
        encoding="utf-8",
    )
    domain = public.create_domain_context(domain_path)
    policy_path = tmp_path / "empty_policy.formatted.txt"

    policy = public.write_empty_policy(domain, policy_path)
    reparsed = public.create_policy(domain, policy_path)

    assert policy.source is CandidateSource.FILE
    assert policy.source_file == policy_path.resolve()
    assert policy_path.read_text(encoding="utf-8") == str(policy.value).rstrip() + "\n"
    assert str(reparsed.value) == str(policy.value)
