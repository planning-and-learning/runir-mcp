from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pyrunir_mcp.candidates import Candidate
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.history import ValidationHistory
from pyrunir_mcp.kr.ps.base.core.features import (
    collect_features as collect_base_features,
    intern_rules as intern_base_rules,
)
from pyrunir_mcp.kr.ps.base.rollout import rollout_artifacts
from pyrunir_mcp.kr.ps.ext.rules import (
    collect_features as collect_ext_features,
    intern_rules as intern_ext_rules,
)
from pyrunir_mcp.kr.ps.execute import run_execute
from pyrunir_mcp.kr.ps.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.frontier import make_ext_frontier_expander, make_frontier_expander
from pyrunir_mcp.kr.ps.proof import build_proof_run
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.writer import Fmt
from pyrunir_mcp.validation import (
    ClassifierProofCounts,
    FailureFingerprint,
    ExecuteModuleProgramResult,
    ExecuteObservationDetails,
    ExecutePolicyResult,
    ObservationDetails,
    ProofObservationDetails,
    ProveClassifierResult,
    ProveModuleProgramResult,
    ProvePolicyResult,
    ValidationObservation,
    ValidationResult,
)


class DumpFormat(StrEnum):
    JSON = "json"
    PSV = "psv"
    MD = "md"


@dataclass(frozen=True, slots=True)
class DumpResult:
    output_dir: Path
    files: tuple[Path, ...]


def _render_formats(formats: tuple[DumpFormat, ...]) -> tuple[Fmt, ...]:
    selected = [fmt.value for fmt in formats]
    return tuple(fmt for fmt in selected if fmt in {"psv", "md", "json"})  # type: ignore[return-value]

def _counts_json(counts: ClassifierProofCounts) -> JsonObject:
    return {
        "states": counts.states,
        "unsolvable": counts.unsolvable,
        "false_positive": counts.false_positive,
        "false_negative": counts.false_negative,
    }


def _observation_details_json(details: ObservationDetails) -> JsonObject:
    if isinstance(details, ExecuteObservationDetails):
        return {
            "num_rollouts": details.num_rollouts,
            "failure": None
            if details.failure_problem_file is None
            else {
                "problem_file": details.failure_problem_file,
                "status": details.failure_status.name
                if details.failure_status is not None
                else None,
            },
        }
    if isinstance(details, ProofObservationDetails):
        return {
            "proof": {
                "status": details.proof_status.name,
                "successful": details.successful,
            }
        }
    return {
        "counts": _counts_json(details.counts),
        "state_graph_status": details.state_graph_status.name
        if details.state_graph_status is not None
        else None,
    }


def _fingerprint_json(fingerprint: FailureFingerprint | None) -> JsonObject | None:
    if fingerprint is None:
        return None
    return {
        "kind": fingerprint.kind.value,
        "status": fingerprint.status.value,
        "problem_file": fingerprint.problem_file,
        "category": fingerprint.category,
        "witness": list(fingerprint.witness),
    }


def _observation_json(observation: ValidationObservation) -> JsonObject:
    return {
        "result_id": observation.result_id,
        "kind": observation.kind.value,
        "status": observation.status.value,
        "candidate_id": observation.candidate_id,
        "classifier_id": observation.classifier_id,
        "fingerprint": _fingerprint_json(observation.fingerprint),
        "details": _observation_details_json(observation.details),
    }


def _candidate_json(candidate: Candidate) -> JsonObject:
    return {
        "type": type(candidate).__name__,
        "id": candidate.id,
        "source": candidate.source.value,
        "source_file": candidate.source_file.as_posix()
        if candidate.source_file is not None
        else None,
    }


def _result_json(result: ValidationResult) -> JsonObject:
    base: JsonObject = {
        "id": result.id,
        "kind": result.kind.value,
        "status": result.status.value,
        "context": {"id": result.context.id, "index": result.context.index},
        "candidate": _candidate_json(result.candidate),
        "observation": _observation_json(result.observation),
    }
    if isinstance(result, (ExecutePolicyResult, ExecuteModuleProgramResult)):
        base["num_rollouts"] = result.num_rollouts
        base["failure"] = (
            None
            if result.failure is None
            else {
                "problem_file": result.failure.task.problem_path.name,
                "status": result.failure.result.status.name,
            }
        )
    elif isinstance(result, (ProvePolicyResult, ProveModuleProgramResult)):
        base["proof"] = {
            "status": result.proof.status.name,
            "successful": bool(result.proof.is_successful()),
        }
    elif isinstance(result, ProveClassifierResult):
        base["counts"] = _counts_json(result.counts)
    return base




def _candidate_source_metadata(result: ValidationResult) -> JsonObject:
    source_file = result.candidate.source_file
    return {
        "candidate_id": result.candidate.id,
        "candidate_type": type(result.candidate).__name__,
        "candidate_source": result.candidate.source.value,
        "candidate_file": source_file.as_posix() if source_file is not None else None,
    }


def _populate_feature_dictionary(dicts: Dictionaries, features: list[object]) -> list[str]:
    for feature in features:
        dicts.feature(feature_key(feature))
    return dicts.feature_symbols()


def _dump_execute_policy_artifacts(
    result: ExecutePolicyResult, output_path: Path, formats: tuple[Fmt, ...]
) -> Path | None:
    if not formats:
        return None
    features = collect_base_features(result.candidate.value)
    dicts = Dictionaries(ext=False)
    feature_symbols = _populate_feature_dictionary(dicts, features)
    intern_base_rules(result.candidate.value, dicts)
    evidence = state_evidence(features, include_facts=True, include_hstar=False, include_hlmcut=False)
    task = result.context.base_task
    proofs_by_seed = {seed: proof for seed, proof in result.successful_results}
    if result.failure is not None:
        proofs_by_seed.setdefault(0, result.failure.result)
    if not proofs_by_seed:
        return None

    def solve(_task: object, seed: int):
        return proofs_by_seed[seed]

    run_execute(
        tool=result.kind.value,
        ext=False,
        output_dir=output_path,
        seeds=sorted(proofs_by_seed),
        tasks=[task],
        solve=solve,
        feature_symbols=feature_symbols,
        evidence=evidence,
        dicts=dicts,
        manifest_metadata=_candidate_source_metadata(result),
        include_hstar=False,
        include_hlmcut=False,
        expander_factory=lambda loaded_task: make_frontier_expander(
            loaded_task.search_context, result.candidate.value, evidence
        ),
        rollout_fallback=(
            (
                lambda loaded_task, **kwargs: rollout_artifacts(
                    loaded_task.search_context,
                    result.candidate.value,
                    features,
                    result.classifier.value,
                    **kwargs,
                )
            )
            if result.classifier is not None
            else None
        ),
        formats=formats,
    )
    manifest = output_path / "manifest.json"
    return manifest if manifest.exists() else None


def _dump_execute_module_program_artifacts(
    result: ExecuteModuleProgramResult, output_path: Path, formats: tuple[Fmt, ...]
) -> Path | None:
    if not formats:
        return None
    features = collect_ext_features(result.candidate.value)
    dicts = Dictionaries(ext=True)
    feature_symbols = _populate_feature_dictionary(dicts, features)
    intern_ext_rules(result.candidate.value, dicts)
    evidence = state_evidence(features, include_facts=True, include_hstar=False, include_hlmcut=False)
    task = result.context.ext_task
    proofs_by_seed = {seed: proof for seed, proof in result.successful_results}
    if result.failure is not None:
        proofs_by_seed.setdefault(0, result.failure.result)
    if not proofs_by_seed:
        return None

    def solve(_task: object, seed: int):
        return proofs_by_seed[seed]

    run_execute(
        tool=result.kind.value,
        ext=True,
        output_dir=output_path,
        seeds=sorted(proofs_by_seed),
        tasks=[task],
        solve=solve,
        feature_symbols=feature_symbols,
        evidence=evidence,
        dicts=dicts,
        manifest_metadata=_candidate_source_metadata(result),
        include_hstar=False,
        include_hlmcut=False,
        expander_factory=lambda loaded_task: make_ext_frontier_expander(
            loaded_task.search_context, result.candidate.value, evidence
        ),
        formats=formats,
    )
    manifest = output_path / "manifest.json"
    return manifest if manifest.exists() else None


def _dump_prove_policy_artifacts(
    result: ProvePolicyResult, output_path: Path, formats: tuple[Fmt, ...]
) -> Path | None:
    if not formats:
        return None
    features = collect_base_features(result.candidate.value)
    dicts = Dictionaries(ext=False)
    feature_symbols = _populate_feature_dictionary(dicts, features)
    intern_base_rules(result.candidate.value, dicts)
    evidence = state_evidence(features, include_facts=True, include_hstar=False, include_hlmcut=False)
    envelope = build_proof_run(
        tool=result.kind.value,
        output_dir=output_path,
        metadata=_candidate_source_metadata(result),
        task=result.context.base_task,
        result=result.proof,
        feature_symbols=feature_symbols,
        dicts=dicts,
        ext=False,
        evidence=evidence,
        expander=make_frontier_expander(result.context.base_task.search_context, result.candidate.value, evidence),
        include_hstar=False,
        include_hlmcut=False,
        formats=formats,
    )
    path = output_path / "run.json"
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _dump_prove_module_program_artifacts(
    result: ProveModuleProgramResult, output_path: Path, formats: tuple[Fmt, ...]
) -> Path | None:
    if not formats:
        return None
    features = collect_ext_features(result.candidate.value)
    dicts = Dictionaries(ext=True)
    feature_symbols = _populate_feature_dictionary(dicts, features)
    intern_ext_rules(result.candidate.value, dicts)
    evidence = state_evidence(features, include_facts=True, include_hstar=False, include_hlmcut=False)
    envelope = build_proof_run(
        tool=result.kind.value,
        output_dir=output_path,
        metadata=_candidate_source_metadata(result),
        task=result.context.ext_task,
        result=result.proof,
        feature_symbols=feature_symbols,
        dicts=dicts,
        ext=True,
        evidence=evidence,
        expander=make_ext_frontier_expander(result.context.ext_task.search_context, result.candidate.value, evidence),
        include_hstar=False,
        include_hlmcut=False,
        formats=formats,
    )
    path = output_path / "run.json"
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _dump_rich_artifacts(result: ValidationResult, output_path: Path, formats: tuple[Fmt, ...]) -> Path | None:
    if isinstance(result, ExecutePolicyResult):
        return _dump_execute_policy_artifacts(result, output_path, formats)
    if isinstance(result, ExecuteModuleProgramResult):
        return _dump_execute_module_program_artifacts(result, output_path, formats)
    if isinstance(result, ProvePolicyResult):
        return _dump_prove_policy_artifacts(result, output_path, formats)
    if isinstance(result, ProveModuleProgramResult):
        return _dump_prove_module_program_artifacts(result, output_path, formats)
    return None

def dump_result(
    result: ValidationResult,
    output_dir: str | Path,
    *,
    formats: tuple[DumpFormat, ...] = (DumpFormat.JSON,),
) -> DumpResult:
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []

    rich_formats = _render_formats(formats)
    if rich_path := _dump_rich_artifacts(result, output_path, rich_formats):
        files.append(rich_path)

    # Always keep the compact machine-readable sidecar; callers use it for state/history plumbing.
    path = output_path / "result.json"
    path.write_text(
        json.dumps(_result_json(result), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    files.append(path)
    return DumpResult(output_dir=output_path, files=tuple(files))


def dump_validation_history(
    history: ValidationHistory,
    output_dir: str | Path,
    *,
    formats: tuple[DumpFormat, ...] = (DumpFormat.JSON,),
) -> DumpResult:
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    if DumpFormat.JSON in formats:
        path = output_path / "history.json"
        payload: JsonObject = {
            "observations": [
                _observation_json(observation) for observation in history.observations
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files.append(path)
    return DumpResult(output_dir=output_path, files=tuple(files))
