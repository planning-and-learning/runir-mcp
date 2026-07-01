from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import StrEnum
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

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
from pyrunir_mcp.kr.ps.execute import RolloutFallbackResult, Task, run_execute
from pyrunir_mcp.kr.ps.feature_evidence import Feature, feature_key, state_evidence
from pyrunir_mcp.kr.ps.frontier import make_ext_frontier_expander, make_frontier_expander
from pyrunir_mcp.kr.ps.proof import ProofResult, StateEvidence, build_proof_run
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


def _format_value(fmt: DumpFormat) -> Fmt:
    value: Literal["psv", "md", "json"] = fmt.value
    return value


def _render_formats(formats: tuple[DumpFormat, ...]) -> tuple[Fmt, ...]:
    return tuple(_format_value(fmt) for fmt in formats)

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
                "status": str(getattr(details.failure_status, "name", details.failure_status))
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
    else:
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


def _populate_feature_dictionary(dicts: Dictionaries, features: Sequence[Feature]) -> list[str]:
    for feature in features:
        dicts.feature(feature_key(feature))
    return dicts.feature_symbols()


def _execute_policy_rollout_fallback(result: ExecutePolicyResult, features: list[Feature]):
    classifier = result.classifier
    if classifier is None:
        return None

    def fallback(
        task: Task,
        *,
        header: list[tuple[str, str]],
        evidence: StateEvidence,
        feature_symbols: list[str],
        dicts: Dictionaries,
    ) -> RolloutFallbackResult:
        return rollout_artifacts(
            task.search_context,
            result.candidate.value,
            features,
            classifier.value,
            evidence,
            feature_symbols=feature_symbols,
            dicts=dicts,
            header=header,
        )

    return fallback


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

    def solve(_task: object, seed: int) -> ProofResult:
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
            _execute_policy_rollout_fallback(result, features)
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

    def solve(_task: object, seed: int) -> ProofResult:
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
    envelope: JsonObject = build_proof_run(
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
    envelope: JsonObject = build_proof_run(
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

def _state_id_sort_key(value: str) -> tuple[int, str]:
    suffix = value[1:] if value.startswith("s") else value
    try:
        return (int(suffix), value)
    except ValueError:
        return (0, value)


def _rotate_smallest_state_id_first(state_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not state_ids:
        return ()
    start = min(range(len(state_ids)), key=lambda index: _state_id_sort_key(state_ids[index]))
    return state_ids[start:] + state_ids[:start]


def _witness_info_from_file(path: Path) -> tuple[str | None, tuple[str, ...]]:
    ids: list[str] = []
    cycle_ids: tuple[str, ...] | None = None
    section: str | None = None
    id_column: int | None = None
    key_column: int | None = None
    value_column: int | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("@"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            id_column = None
            key_column = None
            value_column = None
            continue
        parts = [part.strip() for part in line.split("|")]
        if section == "cycle":
            if key_column is None or value_column is None:
                if "key" in parts and "value" in parts:
                    key_column = parts.index("key")
                    value_column = parts.index("value")
                continue
            if (
                key_column < len(parts)
                and value_column < len(parts)
                and parts[key_column] == "cycle_state_indices"
            ):
                cycle_ids = tuple(value for value in parts[value_column].split(",") if value)
        elif section == "state":
            if id_column is None:
                if "id" in parts:
                    id_column = parts.index("id")
                continue
            if id_column < len(parts) and parts[id_column]:
                ids.append(parts[id_column])
    if cycle_ids is not None:
        return "cycle", cycle_ids
    return None, tuple(ids)


def _refresh_execute_fingerprint_from_manifest(result: ValidationResult, manifest_path: Path | None) -> None:
    if not isinstance(result, (ExecutePolicyResult, ExecuteModuleProgramResult)):
        return
    if manifest_path is None or not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = manifest.get("distinct_failures")
    if not isinstance(failures, list) or not failures:
        return
    failure = failures[0]
    if not isinstance(failure, dict):
        return
    category = failure.get("failure_category")
    problem_file = failure.get("problem_file")
    if not isinstance(category, str):
        return
    witness_ids: tuple[str, ...] = ()
    witness_path = failure.get("witness_path")
    if isinstance(witness_path, str):
        category_override, witness_ids = _witness_info_from_file(Path(witness_path))
        if category_override is not None:
            category = category_override
        if category == "cycle":
            witness_ids = _rotate_smallest_state_id_first(witness_ids)
    fingerprint = FailureFingerprint(
        kind=result.kind,
        status=result.status,
        problem_file=problem_file if isinstance(problem_file, str) else None,
        category=category,
        witness=witness_ids,
    )
    object.__setattr__(
        result,
        "observation",
        replace(result.observation, fingerprint=fingerprint),
    )


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
    rich_path = _dump_rich_artifacts(result, output_path, rich_formats)
    if rich_path:
        files.append(rich_path)
    _refresh_execute_fingerprint_from_manifest(result, rich_path)

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
