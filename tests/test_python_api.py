from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pyrunir_mcp as public
from pyrunir.kr.ps.base import Sketch
from pytyr.planning import SearchStatus

from pyrunir_mcp.kr.ps.base.core.data_loader import (
    LoadedLiftedSearchContext as BaseLoadedLiftedSearchContext,
)
from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext as BaseLoadedSearchTaskContext
from pyrunir_mcp.kr.ps.ext.core.data_loader import (
    LoadedLiftedSearchContext as ExtLoadedLiftedSearchContext,
)
from pyrunir_mcp.kr.ps.ext.core.data_loader import LoadedSearchContext as ExtLoadedSearchTaskContext
from pyrunir_mcp import (
    CandidateSource,
    ClassifierObservationDetails,
    ClassifierProofCounts,
    TaskContext,
    DumpFormat,
    ExecuteObservationDetails,
    FailureFingerprint,
    Policy,
    ValidationKind,
    ValidationHistory,
    ValidationObservation,
    ValidationStatus,
    dump_validation_history,
)
from pyyggdrasil.execution import ExecutionContext


def _task_context(tmp_path: Path) -> TaskContext:
    return TaskContext(
        id="task_000001",
        index=1,
        problem_file=tmp_path / "problem.pddl",
        execution_context=cast(ExecutionContext, None),
        base_task=cast(BaseLoadedSearchTaskContext, None),
        base_lifted_task=cast(BaseLoadedLiftedSearchContext, None),
        ext_task=cast(ExtLoadedSearchTaskContext, None),
        ext_lifted_task=cast(ExtLoadedLiftedSearchContext, None),
    )


def test_public_exports_use_typed_names() -> None:
    assert public.Policy is Policy
    assert public.ExecuteObservationDetails is ExecuteObservationDetails
    assert public.ClassifierObservationDetails is ClassifierObservationDetails


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
        witness=("7",),
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
