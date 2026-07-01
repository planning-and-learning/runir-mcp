from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pyrunir_mcp as public
from pyrunir.kr.ps.base import Sketch
from pytyr.planning import SearchStatus

from pyrunir_mcp.validation import rotate_smallest_state_id_first
from pyrunir_mcp.dumping import refresh_execute_fingerprint_from_manifest
from pyrunir_mcp.kr.ps.execute import with_docs_header
from pyrunir_mcp.tables import Document, Table

from pyrunir_mcp import (
    CandidateSource,
    ClassifierObservationDetails,
    ClassifierProofCounts,
    DumpFormat,
    ExecuteObservationDetails,
    ExecutePolicyResult,
    TaskContext,
    FailureFingerprint,
    Policy,
    ValidationKind,
    ValidationHistory,
    ValidationObservation,
    ValidationStatus,
    dump_validation_history,
)



def test_public_exports_use_typed_names() -> None:
    assert public.Policy is Policy
    assert public.ExecuteObservationDetails is ExecuteObservationDetails
    assert public.ClassifierObservationDetails is ClassifierObservationDetails


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


def test_execute_fallback_docs_are_reheaded_after_reclassification() -> None:
    old_header = [("id", "open_state-001"), ("category", "open_state")]
    new_header = [("id", "deadend-001"), ("category", "deadend")]
    table = Table("state", ["id", "flags"], [["s87", "WITNESS,DEADEND"]])
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
@category open_state

[cycle]
key|value
cycle_state_indices|s8666,s8698,s8793,s8697,s8666

[states]
id|flags
s0|INIT
s8666|OPEN,WITNESS,CYCLE
s8698|
s8793|
s8697|
s8666|OPEN,WITNESS,CYCLE
""",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "distinct_failures": [
                    {
                        "failure_category": "open_state",
                        "problem_file": "p03.pddl",
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

    refresh_execute_fingerprint_from_manifest(result, manifest_path)

    assert result.observation.fingerprint == FailureFingerprint(
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

[state]
id|flags|f0
s339|WITNESS,DEADEND|2

[facts]
state|atoms
s339|p0
""",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "distinct_failures": [
                    {
                        "failure_category": "deadend",
                        "problem_file": "p01.pddl",
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

    refresh_execute_fingerprint_from_manifest(result, manifest_path)

    assert result.observation.fingerprint == FailureFingerprint(
        kind=ValidationKind.BASE_EXECUTE,
        status=ValidationStatus.FAILURE,
        problem_file="p01.pddl",
        category="deadend",
        witness=("s339",),
    )


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
            "fingerprint": None,
            "details": {
                "num_rollouts": 3,
                "failure": {"problem_file": "p01.pddl", "status": "FAILED"},
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

    assert payload["observations"][0]["fingerprint"] is None
    assert payload["observations"][0]["details"] == {
        "counts": {
            "states": 10,
            "unsolvable": 4,
            "false_positive": 1,
            "false_negative": 2,
        },
        "state_graph_status": "OUT_OF_TIME",
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

    assert policy.source is CandidateSource.EMPTY
    assert policy.source_file == policy_path.resolve()
    assert policy_path.read_text(encoding="utf-8") == str(policy.value).rstrip() + "\n"
    assert str(reparsed.value) == str(policy.value)
