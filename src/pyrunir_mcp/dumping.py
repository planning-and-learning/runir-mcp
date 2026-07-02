from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import StrEnum
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, cast

from pyrunir_mcp.candidates import Candidate
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.history import ValidationHistory
from pyrunir_mcp.kr.ps.base.core.features import (
    collect_features as collect_base_features,
    intern_rules as intern_base_rules,
)
from pyrunir_mcp.kr.ps.base.rollout import rollout_artifacts
from pyrunir_mcp.kr.ps.ext.termination.serialize import (
    TerminationCounterexample,
    counterexample_to_data,
)
from pyrunir_mcp.kr.ps.ext.rules import (
    collect_features as collect_ext_features,
    intern_rules as intern_ext_rules,
)
from pyrunir_mcp.kr.ps.execute import RolloutFallbackResult, Task, run_execute
from pyrunir_mcp.kr.ps.feature_evidence import Feature, feature_key, state_atom_evidence, state_evidence
from pyrunir_mcp.kr.ps.frontier import make_ext_frontier_expander, make_frontier_expander
from pyrunir_mcp.kr.uns.serialize import feature_symbols as classifier_feature_symbols
from pyrunir_mcp.kr.ps.plan_trace import plan_open_state_trace
from pyrunir_mcp.kr.ps.proof import ProofResult, StateEvidence, build_proof_run
from pytyr.planning.ground import State as GroundState
from pyrunir_mcp.output.classifier import ClassifierRow, classifier_witness
from pyrunir_mcp.output.dictionaries import AtomKind, Dictionaries
from pyrunir_mcp.output.run import RunCategory, RunItem, RunItemCategory, RunStatus, build_run_envelope
from pyrunir_mcp.output.termination import (
    TerminationDictionaries,
    TerminationEdge,
    TerminationVertex,
    counterexample_document as termination_counterexample_document,
)
from pyrunir_mcp.output.writer import Artifact, Fmt
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
    ProveTerminationResult,
    SearchBudget,
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


def _budget_json(budget: SearchBudget) -> JsonObject:
    return {
        "max_num_states": budget.max_num_states,
        "max_time_seconds": budget.max_time_seconds,
    }

def _observation_details_json(details: ObservationDetails) -> JsonObject:
    from pyrunir_mcp.validation import TerminationObservationDetails

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
    if isinstance(details, TerminationObservationDetails):
        return {
            "program_status": details.program_status.name,
            "terminating": details.terminating,
            "nonterminating_modules": list(details.nonterminating_modules),
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


def _result_context_json(result: ValidationResult) -> JsonObject:
    if isinstance(result, ProveTerminationResult):
        return {
            "id": result.domain_context.id,
            "domain_file": result.domain_context.domain_file.as_posix(),
        }
    return {"id": result.context.id, "index": result.context.index}


def _result_json(result: ValidationResult) -> JsonObject:
    base: JsonObject = {
        "id": result.id,
        "kind": result.kind.value,
        "status": result.status.value,
        "context": _result_context_json(result),
        "candidate": _candidate_json(result.candidate),
        "observation": _observation_json(result.observation),
    }
    if isinstance(result, (ExecutePolicyResult, ExecuteModuleProgramResult, ProvePolicyResult, ProveModuleProgramResult)):
        base["search_budget"] = _budget_json(result.search_budget)
        base["plan_trace_budget"] = _budget_json(result.plan_trace_budget)
    elif isinstance(result, ProveClassifierResult):
        base["search_budget"] = _budget_json(result.search_budget)
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
        base["failure_seeds"] = [seed for seed, _failure in result.failure_results]
        base["success_seeds"] = [seed for seed, _proof in result.successful_results]
    elif isinstance(result, (ProvePolicyResult, ProveModuleProgramResult)):
        base["proof"] = {
            "status": result.proof.status.name,
            "successful": bool(result.proof.is_successful()),
        }
    elif isinstance(result, ProveTerminationResult):
        base["termination"] = {
            "program_status": result.program_result.status.name,
            "successful": bool(result.program_result.is_terminating()),
            "nonterminating_modules": list(result.nonterminating_modules),
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



def _populate_state_atoms(dicts: Dictionaries, state: GroundState) -> None:
    for kind, atom in state_atom_evidence(state):
        dicts.atom(AtomKind(kind), atom)


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
    _populate_state_atoms(dicts, result.context.base_task.search_context.state_repository.get_initial_state())
    task = result.context.base_task
    proofs_by_seed = {seed: proof for seed, proof in result.successful_results}
    proofs_by_seed.update((seed, failure.result) for seed, failure in result.failure_results)
    if result.failure is not None and not result.failure_results:
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
        open_state_plan=lambda _task, state: plan_open_state_trace(
            ground_context=result.context.base_task.search_context,
            lifted_context=result.context.base_lifted_task.search_context,
            state=state,
            features=features,
            dicts=dicts,
            max_num_states=result.plan_trace_budget.max_num_states,
            max_time_seconds=result.plan_trace_budget.max_time_seconds,
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
    _populate_state_atoms(dicts, result.context.ext_task.search_context.state_repository.get_initial_state())
    task = result.context.ext_task
    proofs_by_seed = {seed: proof for seed, proof in result.successful_results}
    proofs_by_seed.update((seed, failure.result) for seed, failure in result.failure_results)
    if result.failure is not None and not result.failure_results:
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
        open_state_plan=lambda _task, state: plan_open_state_trace(
            ground_context=result.context.ext_task.search_context,
            lifted_context=result.context.ext_lifted_task.search_context,
            state=state,
            features=features,
            dicts=dicts,
            max_num_states=result.plan_trace_budget.max_num_states,
            max_time_seconds=result.plan_trace_budget.max_time_seconds,
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
    _populate_state_atoms(dicts, result.context.base_task.search_context.state_repository.get_initial_state())
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
        open_state_plan=lambda state: plan_open_state_trace(
            ground_context=result.context.base_task.search_context,
            lifted_context=result.context.base_lifted_task.search_context,
            state=state,
            features=features,
            dicts=dicts,
            max_num_states=result.plan_trace_budget.max_num_states,
            max_time_seconds=result.plan_trace_budget.max_time_seconds,
        ),
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
    _populate_state_atoms(dicts, result.context.ext_task.search_context.state_repository.get_initial_state())
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
        open_state_plan=lambda state: plan_open_state_trace(
            ground_context=result.context.ext_task.search_context,
            lifted_context=result.context.ext_lifted_task.search_context,
            state=state,
            features=features,
            dicts=dicts,
            max_num_states=result.plan_trace_budget.max_num_states,
            max_time_seconds=result.plan_trace_budget.max_time_seconds,
        ),
        include_hstar=False,
        include_hlmcut=False,
    )
    path = output_path / "run.json"
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path




def _dump_prove_classifier_artifacts(
    result: ProveClassifierResult, output_path: Path, formats: tuple[Fmt, ...]
) -> Path | None:
    if not formats or not result.mistakes:
        return None
    dicts = Dictionaries(ext=False)
    feature_symbols = classifier_feature_symbols(result.candidate.value)
    for symbol in feature_symbols:
        dicts.feature(symbol)
    for kind, atom in result.atoms:
        dicts.atom(AtomKind(kind), atom)

    artifacts: dict[str, Artifact] = {}
    items: list[RunItem] = []
    for mistake in result.mistakes:
        category = RunItemCategory(mistake.category)
        fluent = tuple(atom for kind, atom in mistake.atoms if kind == AtomKind.FLUENT.value)
        derived = tuple(atom for kind, atom in mistake.atoms if kind == AtomKind.DERIVED.value)
        row = ClassifierRow(
            id=mistake.id,
            category=category,
            state=mistake.state,
            features=mistake.features,
            fluent=fluent,
            derived=derived,
        )
        witness_name = f"failures/{mistake.id}/witness"
        artifacts[witness_name] = classifier_witness(
            row,
            feature_symbols,
            dicts,
            header=[
                ("tool", result.kind.value),
                ("id", mistake.id),
                ("category", mistake.category),
                ("task", result.context.problem_file.name),
            ],
        )
        items.append(
            RunItem(
                id=mistake.id,
                category=category,
                task=result.context.problem_file.name,
                witness=witness_name,
            )
        )

    envelope = build_run_envelope(
        tool=result.kind.value,
        status=RunStatus.FAILURE if result.status.value == RunStatus.FAILURE.value else RunStatus.SUCCESS,
        output_dir=output_path,
        metadata={**_candidate_source_metadata(result), "counts": _counts_json(result.counts)},
        dictionary_tables=dicts.tables(),
        artifacts=artifacts,
        items=items,
        category=RunCategory.COUNTEREXAMPLE,
        formats=formats,
    )
    path = output_path / "run.json"
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _json_int(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _json_str_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(key): str(item) for key, item in mapping.items()}


def _termination_vertices_edges(
    counterexample: TerminationCounterexample,
) -> tuple[list[TerminationVertex], list[TerminationEdge]]:
    data = counterexample_to_data(counterexample)
    raw_vertices = data.get("vertices", [])
    raw_edges = data.get("edges", [])
    vertices: list[TerminationVertex] = []
    if isinstance(raw_vertices, list):
        for raw in raw_vertices:
            if not isinstance(raw, dict):
                continue
            vertices.append(
                TerminationVertex(
                    _json_int(raw.get("index"), len(vertices)),
                    str(raw.get("memory_state", "")),
                    concepts=_json_str_dict(raw.get("concepts")),
                    booleans=_json_str_dict(raw.get("booleans")),
                    numericals=_json_str_dict(raw.get("numericals")),
                )
            )
    edges: list[TerminationEdge] = []
    if isinstance(raw_edges, list):
        for raw in raw_edges:
            if not isinstance(raw, dict):
                continue
            edges.append(
                TerminationEdge(
                    _json_int(raw.get("index"), len(edges)),
                    _json_int(raw.get("source"), 0),
                    _json_int(raw.get("target"), 0),
                    str(raw.get("rule", "")),
                    numerical_changes=_json_str_dict(raw.get("numerical_changes")),
                )
            )
    return vertices, edges


def _dump_prove_termination_artifacts(
    result: ProveTerminationResult, output_path: Path, formats: tuple[Fmt, ...]
) -> Path | None:
    if not formats:
        return None
    dicts = TerminationDictionaries()
    artifacts: dict[str, Artifact] = {}
    items: list[RunItem] = []
    modules = result.candidate.value.get_modules()
    for index, module_result in enumerate(result.program_result.get_module_results()):
        if bool(module_result.is_terminating()):
            continue
        raw_counterexample = module_result.get_counterexample()
        if raw_counterexample is None:
            continue
        counterexample = cast(TerminationCounterexample, raw_counterexample)
        module_name = (
            str(modules[index].get_name())
            if index < len(modules) and hasattr(modules[index], "get_name")
            else f"module_{index}"
        )
        item_id = f"structural_termination-{len(items) + 1:03d}"
        vertices, edges = _termination_vertices_edges(counterexample)
        witness_name = f"failures/{item_id}/witness"
        artifacts[witness_name] = termination_counterexample_document(
            header=[
                ("tool", result.kind.value),
                ("id", item_id),
                ("category", "structural_termination"),
                ("module", module_name),
            ],
            vertices=vertices,
            edges=edges,
            dicts=dicts,
        )
        items.append(
            RunItem(
                id=item_id,
                category=RunItemCategory.STRUCTURAL_TERMINATION,
                task=module_name,
                witness=witness_name,
            )
        )
    envelope = build_run_envelope(
        tool="runir.ps.ext.prove_termination",
        status=RunStatus.SUCCESS if result.status.value == RunStatus.SUCCESS.value else RunStatus.FAILURE,
        output_dir=output_path,
        metadata={
            **_candidate_source_metadata(result),
            "program_status": result.program_result.status.name,
            "nonterminating_modules": list(result.nonterminating_modules),
        },
        dictionary_tables=dicts.tables(),
        artifacts=artifacts,
        items=items,
        failure_category=RunItemCategory.STRUCTURAL_TERMINATION if items else None,
        category=RunCategory.SUCCESS if result.status.value == RunStatus.SUCCESS.value else RunCategory.COUNTEREXAMPLE,
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
    if isinstance(result, ProveClassifierResult):
        return _dump_prove_classifier_artifacts(result, output_path, formats)
    return _dump_prove_termination_artifacts(result, output_path, formats)

def _state_id_sort_key(value: str) -> tuple[int, str]:
    suffix = value[1:] if value.startswith("s") else value
    try:
        return (int(suffix), value)
    except ValueError:
        return (0, value)


def _cycle_part_key(value: str) -> tuple[tuple[int, str], tuple[int, str], tuple[int, str]]:
    parts = value.split("|", 2)
    if len(parts) == 3:
        module, memory, state = parts
        return ((0, module), (0, memory), _state_id_sort_key(state))
    return ((0, ""), (0, ""), _state_id_sort_key(value))


def rotate_smallest_state_id_first(state_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not state_ids:
        return ()
    closed = len(state_ids) > 1 and state_ids[0] == state_ids[-1]
    ring = state_ids[:-1] if closed else state_ids
    start = min(range(len(ring)), key=lambda index: _cycle_part_key(ring[index]))
    rotated = ring[start:] + ring[:start]
    return (*rotated, rotated[0]) if closed and rotated else rotated


def _witness_info_from_file(path: Path) -> tuple[str | None, tuple[str, ...]]:
    ids: list[str] = []
    cycle_ids: tuple[str, ...] | None = None
    section: str | None = None
    id_column: int | None = None
    module_column: int | None = None
    memory_column: int | None = None
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
        elif section in {"state", "states"}:
            if id_column is None:
                if "id" in parts:
                    id_column = parts.index("id")
                elif "state" in parts:
                    id_column = parts.index("state")
                module_column = parts.index("module") if "module" in parts else None
                memory_column = parts.index("memory") if "memory" in parts else None
                continue
            if id_column < len(parts) and parts[id_column]:
                state_id = parts[id_column]
                if (
                    module_column is not None
                    and memory_column is not None
                    and module_column < len(parts)
                    and memory_column < len(parts)
                    and parts[module_column]
                    and parts[memory_column]
                ):
                    ids.append(f"{parts[module_column]}|{parts[memory_column]}|{state_id}")
                else:
                    ids.append(state_id)
    if cycle_ids is not None:
        return "cycle", cycle_ids
    return None, tuple(ids)


def refresh_execute_fingerprint_from_manifest(result: ValidationResult, manifest_path: Path | None) -> None:
    if not isinstance(result, (ExecutePolicyResult, ExecuteModuleProgramResult)):
        return
    if manifest_path is None or not manifest_path.exists():
        return
    manifest = cast(JsonObject, json.loads(manifest_path.read_text(encoding="utf-8")))
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
            witness_ids = rotate_smallest_state_id_first(witness_ids)
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
    refresh_execute_fingerprint_from_manifest(result, rich_path)

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
