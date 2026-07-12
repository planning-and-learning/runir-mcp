from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pyrunir.kr.ps.base import Sketch
from pytyr.planning import SearchStatus

import pyrunir_mcp as public
from pyrunir_mcp import (
    CandidateSource,
    ClassifierObservationDetails,
    ClassifierProofCounts,
    DumpFormat,
    ExecuteObservationDetails,
    ExecutePolicyResult,
    FailureFingerprint,
    Policy,
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
    execute_module_program,
    prove_termination,
)
from pyrunir_mcp.dumping import execute_observation_from_manifest
from pyrunir_mcp.kr.ps.execute import with_docs_header
from pyrunir_mcp.tables import Document, Table
from pyrunir_mcp.validation import rotate_smallest_state_id_first


def test_public_exports_use_typed_names() -> None:
    assert public.Policy is Policy
    assert public.ExecuteObservationDetails is ExecuteObservationDetails
    assert public.ClassifierObservationDetails is ClassifierObservationDetails


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
    assert rotate_smallest_state_id_first(
        ["M1|m0|s1", "M0|m2|s0", "M0|m1|s2", "M1|m0|s1"]
    ) == (
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
    assert (output_dir / "summary.psv").is_file()
    assert witness.is_file()
    assert atoms.is_file()
    assert "[states]" in witness.read_text(encoding="utf-8")
    assert "[facts]" in witness.read_text(encoding="utf-8")
    assert "p0|fluent_atoms|" in atoms.read_text(encoding="utf-8")


def test_empty_module_program_execute_dumps_open_state_artifacts(tmp_path: Path) -> None:
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

    result = execute_module_program(
        task,
        program,
        num_rollouts=1,
        random_seed_start=0,
        search_budget=SearchBudget(max_num_states=200, max_time_seconds=5.0),
        plan_trace_budget=SearchBudget(max_num_states=10_000, max_time_seconds=5.0),
    )
    dumped = dump_result(result, tmp_path / "ext_execute", formats=(DumpFormat.PSV, DumpFormat.JSON))

    output_dir = dumped.output_dir
    witness = output_dir / "failures" / "open_state-001" / "witness.psv"
    trace = output_dir / "failures" / "open_state-001" / "trace.psv"
    successors = output_dir / "failures" / "open_state-001" / "successors.psv"

    assert result.status.value == "failure"
    assert witness.is_file()
    assert trace.is_file()
    assert successors.is_file()
    witness_text = witness.read_text(encoding="utf-8")
    assert "@category open_state" in witness_text
    assert "[states]" in witness_text
    assert "[transitions]" in trace.read_text(encoding="utf-8")

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
    classified = execute_module_program(task, program, classifier=classifier)
    classified_dump = dump_result(
        classified,
        tmp_path / "ext_execute_classified",
        formats=(DumpFormat.PSV,),
    )
    classified_witness = (
        classified_dump.output_dir / "failures" / "deadend-001" / "witness.psv"
    )

    assert classified.rollout_results[0][1].outcome.value == "unsolvable"
    assert classified_witness.is_file()
    assert "witness,deadend" in classified_witness.read_text(encoding="utf-8")
    assert not (
        classified_dump.output_dir / "failures" / "deadend-001" / "successors.psv"
    ).exists()


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
    dumped = dump_result(result, tmp_path / "ext_termination", formats=(DumpFormat.PSV, DumpFormat.JSON))

    output_dir = dumped.output_dir
    assert (output_dir / "result.json").is_file()
    run_json = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))

    assert result.status.value == "success"
    assert run_json["tool"] == "runir.ps.ext.prove_termination"
    assert (output_dir / "summary.psv").is_file()
    assert (output_dir / "dicts" / "variables.psv").is_file()


def test_execute_fallback_docs_are_reheaded_after_reclassification() -> None:
    old_header = [("id", "open_state-001"), ("category", "open_state")]
    new_header = [("id", "deadend-001"), ("category", "deadend")]
    table = Table("state", ["id", "flags"], [["s87", "witness,deadend"]])
    witness = Document(old_header, [table])
    trace = Document(old_header, [table])

    updated_witness, updated_trace, updated_successors = with_docs_header(
        (witness, trace, None), new_header
    )

    assert updated_witness.header == new_header
    assert updated_trace is not None
    assert updated_trace.header == new_header
    assert updated_successors is None
    assert witness.header == old_header


def test_execute_fingerprint_refresh_promotes_cycle_witness(tmp_path: Path) -> None:
    witness_path = tmp_path / "cycle_witness.psv"
    witness_path.write_text(
        """@tool base_execute
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
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=ExecuteObservationDetails("p03.pddl", SearchStatus.FAILED, 1),
        fingerprint=None,
    )
    result = ExecutePolicyResult(
        "result_000001",
        ValidationKind.BASE_EXECUTE,
        ValidationStatus.FAILURE,
        cast(TaskContext, None),
        cast(Policy, None),
        observation,
        None,
        None,
        (),
        1,
    )

    refreshed = execute_observation_from_manifest(result, manifest_path)

    assert result.observation.fingerprint is None
    assert refreshed.fingerprint == FailureFingerprint(
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        problem_file="p03.pddl",
        category="cycle",
        witness=("s8666", "s8698", "s8793", "s8697", "s8666"),
    )


def test_execute_fingerprint_refresh_uses_manifest_witness(tmp_path: Path) -> None:
    witness_path = tmp_path / "witness.psv"
    witness_path.write_text(
        """@tool base_execute
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
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        problem_file="p01.pddl",
        category="open_state",
        witness=("s0",),
    )
    observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=ExecuteObservationDetails("p01.pddl", SearchStatus.FAILED, 1),
        fingerprint=original,
    )
    result = ExecutePolicyResult(
        "result_000001",
        ValidationKind.BASE_EXECUTE,
        ValidationStatus.FAILURE,
        cast(TaskContext, None),
        cast(Policy, None),
        observation,
        None,
        None,
        (),
        1,
    )

    refreshed = execute_observation_from_manifest(result, manifest_path)

    assert result.observation.fingerprint == original
    assert refreshed.fingerprint == FailureFingerprint(
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        problem_file="p01.pddl",
        category="deadend",
        witness=("s339",),
    )


def test_dump_result_reports_reserved_rich_output_dir(tmp_path: Path) -> None:
    domain_file = tmp_path / "domain.pddl"
    domain_file.write_text("""(define (domain seq)
  (:requirements :strips)
  (:predicates (a))
  (:action setA :parameters () :precondition () :effect (a)))
""", encoding="utf-8")
    domain = create_domain_context(domain_file)
    program = create_module_program(domain, None)
    first = dump_result(prove_termination(domain, program), tmp_path / "termination", formats=(DumpFormat.PSV,))
    second = dump_result(prove_termination(domain, program), tmp_path / "termination", formats=(DumpFormat.PSV,))

    assert first.output_dir == (tmp_path / "termination").resolve()
    assert second.output_dir == (tmp_path / "termination" / "run-002").resolve()
    assert (second.output_dir / "run.json").is_file()
    assert (second.output_dir / "result.json").is_file()
    assert (second.output_dir / "summary.psv").is_file()


def test_validation_history_keeps_typed_observations_until_dump(tmp_path: Path) -> None:
    history = ValidationHistory()
    observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=ExecuteObservationDetails(
            failure_problem_file="p01.pddl",
            failure_status=SearchStatus.FAILED,
            num_rollouts=3,
        ),
    )
    feedback = history.fold(observation)

    assert feedback.repeated is False
    assert feedback.previous_occurrences == 0
    assert isinstance(history.observations[0].details, ExecuteObservationDetails)
    assert history.observations[0].details.failure_status is SearchStatus.FAILED

    dumped = dump_validation_history(history, tmp_path / "history", formats=(DumpFormat.JSON,))
    assert dumped.files == (tmp_path / "history" / "history.json",)
    payload = json.loads(dumped.files[0].read_text(encoding="utf-8"))

    assert payload["observations"] == [
        {
            "result_id": "result_000001",
            "kind": "base_execute",
            "status": "failure",
            "candidate_id": "policy_000001",
            "classifier_id": None,
            "witness": None,
            "details": {
                "rollout_count": 3,
                "failure": {"task_file": "p01.pddl", "status": "failed"},
            },
        }
    ]


def test_history_fold_reports_repeated_observations() -> None:
    history = ValidationHistory()
    observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=ExecuteObservationDetails(None, None, 1),
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
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        problem_file="p01.pddl",
        category="open_state",
        witness=("s7",),
    )
    first_observation = ValidationObservation(
        result_id="result_000001",
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000001",
        classifier_id=None,
        details=ExecuteObservationDetails("p01.pddl", SearchStatus.FAILED, 1),
        fingerprint=fingerprint,
    )
    second_observation = ValidationObservation(
        result_id="result_000002",
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        candidate_id="policy_000002",
        classifier_id=None,
        details=ExecuteObservationDetails("p01.pddl", SearchStatus.FAILED, 1),
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
    domain_path.write_text("""(define (domain seq)
  (:requirements :strips)
  (:predicates (a))
  (:action setA :parameters () :precondition () :effect (a)))
""", encoding="utf-8")
    domain = public.create_domain_context(domain_path)
    policy_path = tmp_path / "empty_policy.formatted.txt"

    policy = public.write_empty_policy(domain, policy_path)
    reparsed = public.create_policy(domain, policy_path)

    assert policy.source is CandidateSource.FILE
    assert policy.source_file == policy_path.resolve()
    assert policy_path.read_text(encoding="utf-8") == str(policy.value).rstrip() + "\n"
    assert str(reparsed.value) == str(policy.value)
