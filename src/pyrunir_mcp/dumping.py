from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, TypeAlias, cast

from pyrunir.kr.ps.ext import Module
from pyrunir.kr.ps.ext.dl import ModuleStructuralTerminationResult

from pyrunir_mcp.artifacts import fresh_output_dir
from pyrunir_mcp.candidates import Candidate
from pyrunir_mcp.enums import (
    AtomKind,
    CounterexampleKind,
    DumpFormat,
    RunCategory,
    RunItemCategory,
    RunStatus,
)
from pyrunir_mcp.history import ValidationHistory
from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.keys import (
    Keys,
    TableColumns,
)
from pyrunir_mcp.kr.ps.base.core.features import (
    collect_features as collect_base_features,
)
from pyrunir_mcp.kr.ps.base.core.features import (
    intern_rules as intern_base_rules,
)
from pyrunir_mcp.kr.ps.classifier import classifier_evidence
from pyrunir_mcp.kr.ps.ext.rules import (
    collect_features as collect_ext_features,
)
from pyrunir_mcp.kr.ps.ext.rules import (
    intern_rules as intern_ext_rules,
)
from pyrunir_mcp.kr.ps.feature_evidence import (
    Feature,
    feature_key,
    state_evidence,
)
from pyrunir_mcp.kr.ps.frontier import make_ext_frontier_expander, make_frontier_expander
from pyrunir_mcp.kr.ps.plan_trace import plan_open_state_trace
from pyrunir_mcp.kr.ps.proof import (
    FailureWitness,
    ProofResult,
    failure_items,
    status_name,
    successful_witness_trace_artifacts,
    witness_artifacts,
    witness_ground_state,
)
from pyrunir_mcp.kr.uns.serialize import feature_symbols as classifier_feature_symbols
from pyrunir_mcp.output.classifier import ClassifierRow, classifier_witness
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.run import (
    RunItem,
    build_run_envelope,
)
from pyrunir_mcp.output.termination import (
    TerminationDictionaries,
    TerminationEdge,
    TerminationVertex,
)
from pyrunir_mcp.output.termination import (
    counterexample_document as termination_counterexample_document,
)
from pyrunir_mcp.output.writer import Artifact, write_run
from pyrunir_mcp.tables import Document, Fmt, Table
from pyrunir_mcp.task_generation import (
    TaskGenerationResult,
    task_generation_json,
    write_task_generation_markdown,
)
from pyrunir_mcp.validation import (
    ClassifierProofCounts,
    FailureFingerprint,
    FindModuleProgramSolutionResult,
    FindPolicySolutionResult,
    FindSolutionObservationDetails,
    ObservationDetails,
    ProveClassifierResult,
    ProvePolicyTerminationResult,
    ProveTerminationResult,
    SearchBudget,
    ValidationObservation,
    ValidationResult,
)


@dataclass(frozen=True, slots=True)
class DumpResult:
    output_dir: Path
    files: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class RichDumpResult:
    output_dir: Path
    primary_file: Path


def _format_value(fmt: DumpFormat) -> Fmt:
    value: Literal["psv", "md", "json"] = fmt.value
    return value


def _render_formats(formats: tuple[DumpFormat, ...]) -> tuple[Fmt, ...]:
    return tuple(_format_value(fmt) for fmt in formats)


def _counts_json(counts: ClassifierProofCounts) -> JsonObject:
    return {
        Keys.STATE_COUNT: counts.states,
        Keys.UNSOLVABLE_STATE_COUNT: counts.unsolvable,
        Keys.FALSE_POSITIVE_COUNT: counts.false_positive,
        Keys.FALSE_NEGATIVE_COUNT: counts.false_negative,
    }


def _budget_json(budget: SearchBudget) -> JsonObject:
    return {
        Keys.MAX_STATE_COUNT: budget.max_num_states,
        Keys.MAX_TIME_SECONDS: budget.max_time_seconds,
    }


def _observation_details_json(details: ObservationDetails) -> JsonObject:
    from pyrunir_mcp.validation import (
        PolicyTerminationObservationDetails,
        TerminationObservationDetails,
    )

    if isinstance(details, FindSolutionObservationDetails):
        return {
            Keys.ROLLOUT_COUNT: details.num_rollouts,
            Keys.UNIVERSAL: details.universal,
            Keys.SUCCESSFUL: details.successful,
            Keys.PROOF_STATUSES: [status.name.lower() for status in details.proof_statuses],
        }
    if isinstance(details, PolicyTerminationObservationDetails):
        return {
            Keys.PROGRAM_STATUS: details.policy_status.name.lower(),
            Keys.SUCCESSFUL: details.terminating,
            Keys.INCOMPLETE_TERMINATION_STATUS: details.incomplete_termination_status.value,
        }
    if isinstance(details, TerminationObservationDetails):
        return {
            Keys.PROGRAM_STATUS: details.program_status.name.lower(),
            Keys.SUCCESSFUL: details.terminating,
            Keys.INCOMPLETE_TERMINATION_STATUS: details.incomplete_termination_status.value,
            Keys.NONTERMINATING_MODULES: list(details.nonterminating_modules),
        }
    return {
        Keys.COUNTS: _counts_json(details.counts),
        Keys.STATE_GRAPH_STATUS: details.state_graph_status.name.lower()
        if details.state_graph_status is not None
        else None,
    }


def _observation_json(observation: ValidationObservation) -> JsonObject:
    return {
        Keys.RESULT_ID: observation.result_id,
        Keys.KIND: observation.kind.value,
        Keys.STATUS: observation.status.value,
        Keys.CANDIDATE_ID: observation.candidate_id,
        Keys.CLASSIFIER_ID: observation.classifier_id,
        Keys.WITNESS: None
        if observation.fingerprint is None
        else list(observation.fingerprint.witness),
        Keys.DETAILS: _observation_details_json(observation.details),
    }


def _candidate_json(candidate: Candidate) -> JsonObject:
    return {
        Keys.ID: candidate.id,
        Keys.CANDIDATE_PATH: candidate.source_file.as_posix()
        if candidate.source_file is not None
        else None,
    }


def _result_context_json(result: ValidationResult) -> JsonObject:
    if isinstance(result, (ProvePolicyTerminationResult, ProveTerminationResult)):
        return {
            Keys.ID: result.domain_context.id,
            Keys.DOMAIN_PATH: result.domain_context.domain_file.as_posix(),
        }
    return {Keys.ID: result.context.id, Keys.INDEX: result.context.index}


def _result_json(
    result: ValidationResult, *, observation: ValidationObservation | None = None
) -> JsonObject:
    observation = result.observation if observation is None else observation
    base: JsonObject = {
        Keys.ID: result.id,
        Keys.KIND: result.kind.value,
        Keys.STATUS: result.status.value,
        Keys.CONTEXT: _result_context_json(result),
        Keys.CANDIDATE: _candidate_json(result.candidate),
        Keys.OBSERVATION: _observation_json(observation),
    }
    if isinstance(result, (FindPolicySolutionResult, FindModuleProgramSolutionResult)):
        base[Keys.SEARCH_BUDGET] = _budget_json(result.search_budget)
        base[Keys.PLAN_TRACE_BUDGET] = _budget_json(result.plan_trace_budget)
        base[Keys.UNIVERSAL] = result.universal
        base[Keys.ROLLOUT_COUNT] = result.num_rollouts
        base[Keys.ROLLOUTS] = [
            {
                Keys.SEED: None if result.universal else seed,
                Keys.STATUS: status_name(proof.status),
                Keys.SUCCESSFUL: bool(proof.is_successful()),
            }
            for seed, proof in result.results
        ]
    elif isinstance(result, ProveClassifierResult):
        base[Keys.SEARCH_BUDGET] = _budget_json(result.search_budget)
        base[Keys.COUNTS] = _counts_json(result.counts)
    elif isinstance(result, ProveTerminationResult):
        base[Keys.TERMINATION] = {
            Keys.PROGRAM_STATUS: result.program_result.status.name.lower(),
            Keys.INCOMPLETE_TERMINATION_STATUS: result.incomplete_termination_status.value,
            Keys.NONTERMINATING_MODULES: list(result.nonterminating_modules),
        }
    else:
        base[Keys.TERMINATION] = {
            Keys.PROGRAM_STATUS: result.policy_result.status.name.lower(),
            Keys.INCOMPLETE_TERMINATION_STATUS: result.incomplete_termination_status.value,
        }
    return base


def _candidate_metadata(result: ValidationResult) -> JsonObject:
    source_file = result.candidate.source_file
    return {
        Keys.CANDIDATE_ID: result.candidate.id,
        Keys.CANDIDATE_PATH: source_file.as_posix() if source_file is not None else None,
    }


def _populate_feature_dictionary(dicts: Dictionaries, features: Sequence[Feature]) -> list[str]:
    for feature in features:
        dicts.feature(feature_key(feature))
    return dicts.feature_symbols()




_FIND_SOLUTION_TOOL = "runir.ps.find_solution"
_FIND_SOLUTION_ORIGIN = "find_solution"
SolutionResult: TypeAlias = FindPolicySolutionResult | FindModuleProgramSolutionResult


@dataclass(frozen=True, slots=True)
class _FailureEvidence:
    seed: int | None
    proof: ProofResult
    kind: CounterexampleKind
    witness: FailureWitness


@dataclass(frozen=True, slots=True)
class _SolutionFailureRow:
    id: str
    category: str
    status: str
    seed: int | None
    problem: str
    witness: str
    witness_trace: str | None
    successors: str | None
    plan_trace: str | None


@dataclass(frozen=True, slots=True)
class _SolutionSuccessRow:
    id: str
    status: str
    seed: int | None
    problem: str
    witness_trace: str


def _artifact_relative(name: str | None, fmt: Fmt) -> str | None:
    return None if name is None else f"{name}.{fmt}"


def _output_dir_from_envelope(envelope: JsonObject, fallback: Path) -> Path:
    output_dir = envelope.get(Keys.OUTPUT_DIR)
    return Path(output_dir) if isinstance(output_dir, str) else fallback


def _solution_header(
    *,
    item_id: str,
    category: str,
    status: str,
    problem: str,
    seed: int | None,
) -> list[tuple[str, str]]:
    header: list[tuple[str, str]] = [
        (Keys.TOOL, _FIND_SOLUTION_TOOL),
        (Keys.ID, item_id),
        (Keys.CATEGORY, category),
        (Keys.STATUS, status),
        (Keys.TASK_FILE, problem),
    ]
    if seed is not None:
        header.append((Keys.SEED, str(seed)))
    return header


def select_failure_evidence(result: SolutionResult) -> tuple[list[_FailureEvidence], int]:
    cycle: _FailureEvidence | None = None
    regular: list[_FailureEvidence] = []
    for raw_seed, proof in result.results:
        seed = None if result.universal else raw_seed
        for kind, witness in failure_items(
            proof,
            max_counterexamples=result.num_rollouts - len(regular),
        ):
            item = _FailureEvidence(seed, proof, kind, witness)
            if kind is CounterexampleKind.CYCLE:
                cycle = cycle or item
            elif len(regular) < result.num_rollouts:
                regular.append(item)
    return ([cycle] if cycle is not None else []) + regular, len(regular)


def _dump_solution_artifacts(
    result: SolutionResult,
    output_path: Path,
    formats: tuple[Fmt, ...],
    *,
    include_witness_trace: bool,
    include_plan_trace: bool,
    include_successors: bool,
) -> RichDumpResult | None:
    if not formats:
        return None

    ext = isinstance(result, FindModuleProgramSolutionResult)
    if ext:
        task = result.context.ext_task
        features = collect_ext_features(
            task.get_module_program(
                result.context.domain_context.planning_domain, result.candidate
            )
        )
    else:
        task = result.context.base_task
        features = collect_base_features(
            task.get_policy(
                result.context.domain_context.planning_domain, result.candidate
            )
        )

    task_context = task.task_context
    problem = task.problem_path.name
    dicts = Dictionaries(task=task_context.search_context.task, ext=ext)
    feature_symbols = _populate_feature_dictionary(dicts, features)
    evidence = classifier_evidence(
        task_context,
        state_evidence(
            task_context,
            features,
            include_facts=True,
            include_hstar=False,
            include_hlmcut=False,
        ),
        task.get_classifier(result.context.domain_context.planning_domain, result.classifier)
        if result.classifier is not None
        else None,
    )
    if isinstance(result, FindModuleProgramSolutionResult):
        program = task.get_module_program(
            result.context.domain_context.planning_domain, result.candidate
        )
        intern_ext_rules(program, dicts)
        expander = (
            make_ext_frontier_expander(task_context, program, evidence)
            if include_successors
            else None
        )
    else:
        policy = task.get_policy(
            result.context.domain_context.planning_domain, result.candidate
        )
        intern_base_rules(policy, dicts)
        expander = (
            make_frontier_expander(task_context, policy, evidence)
            if include_successors
            else None
        )

    output_path = fresh_output_dir(output_path)
    artifacts: dict[str, Artifact] = {}
    failure_rows: list[_SolutionFailureRow] = []
    success_rows: list[_SolutionSuccessRow] = []
    category_counts: dict[str, int] = {}
    selected_failures, regular_failure_count = select_failure_evidence(result)

    for selected in selected_failures:
        category = selected.kind.value
        category_counts[category] = category_counts.get(category, 0) + 1
        item_id = f"{category}-{category_counts[category]:03d}"
        native_status = status_name(selected.proof.status)
        header = _solution_header(
            item_id=item_id,
            category=category,
            status=native_status,
            problem=problem,
            seed=selected.seed,
        )
        witness, witness_trace, successors = witness_artifacts(
            selected.proof.graph,
            selected.kind,
            selected.witness,
            evidence,
            feature_symbols=feature_symbols,
            dicts=dicts,
            ext=ext,
            header=header,
            expander=expander,
            include_witness_trace=include_witness_trace,
            include_successors=include_successors,
            include_hstar=False,
            include_hlmcut=False,
        )
        witness_name = f"failures/{item_id}/witness"
        witness_trace_name = f"failures/{item_id}/witness_trace" if witness_trace is not None else None
        successors_name = (
            f"failures/{item_id}/successors" if successors is not None else None
        )
        plan_trace_name: str | None = None
        artifacts[witness_name] = witness
        if witness_trace is not None and witness_trace_name is not None:
            artifacts[witness_trace_name] = witness_trace
        if successors is not None and successors_name is not None:
            artifacts[successors_name] = successors
        if include_plan_trace and selected.kind is CounterexampleKind.OPEN_STATE:
            plan_trace = plan_open_state_trace(
                task_context=task_context,
                state=witness_ground_state(selected.proof.graph, selected.witness),
                features=features,
                dicts=dicts,
                max_num_states=result.plan_trace_budget.max_num_states,
                max_time_seconds=result.plan_trace_budget.max_time_seconds,
            )
            if plan_trace is not None:
                plan_trace_name = f"failures/{item_id}/plan_trace"
                artifacts[plan_trace_name] = Document(
                    header=[*header, (Keys.ORIGIN, "ff")], sections=plan_trace.sections
                )
        failure_rows.append(
            _SolutionFailureRow(
                item_id,
                category,
                native_status,
                selected.seed,
                problem,
                witness_name,
                witness_trace_name,
                successors_name,
                plan_trace_name,
            )
        )

    remaining = result.num_rollouts - regular_failure_count if include_witness_trace else 0
    for raw_seed, proof in result.results:
        if remaining == 0:
            break
        seed = None if result.universal else raw_seed
        witness_traces = successful_witness_trace_artifacts(
            proof.graph,
            evidence,
            max_witness_traces=remaining,
            feature_symbols=feature_symbols,
            dicts=dicts,
            ext=ext,
            header=[],
            include_hstar=False,
            include_hlmcut=False,
        )
        for witness_trace in witness_traces:
            item_id = f"success-{len(success_rows) + 1:03d}"
            native_status = status_name(proof.status)
            witness_trace_name = f"successes/{item_id}/witness_trace"
            artifacts[witness_trace_name] = Document(
                header=_solution_header(
                    item_id=item_id,
                    category=RunItemCategory.SUCCESS.value,
                    status=native_status,
                    problem=problem,
                    seed=seed,
                ),
                sections=witness_trace.sections,
            )
            success_rows.append(
                _SolutionSuccessRow(item_id, native_status, seed, problem, witness_trace_name)
            )
            remaining -= 1

    primary_format = formats[0]
    artifacts[Keys.FAILURES] = Table(
        name=Keys.FAILURES,
        columns=[
            Keys.ID,
            Keys.CATEGORY,
            Keys.STATUS,
            Keys.SEED,
            Keys.TASK_FILE,
            Keys.ORIGIN,
            Keys.WITNESS_TRACE,
            Keys.WITNESS,
            Keys.SUCCESSORS,
            Keys.PLAN_TRACE,
        ],
        rows=[
            [
                row.id,
                row.category,
                row.status,
                row.seed,
                row.problem,
                _FIND_SOLUTION_ORIGIN,
                _artifact_relative(row.witness_trace, primary_format),
                _artifact_relative(row.witness, primary_format),
                _artifact_relative(row.successors, primary_format),
                _artifact_relative(row.plan_trace, primary_format),
            ]
            for row in failure_rows
        ],
    )
    artifacts[Keys.SUCCESSES] = Table(
        name=Keys.SUCCESSES,
        columns=[
            Keys.ID,
            Keys.CATEGORY,
            Keys.STATUS,
            Keys.SEED,
            Keys.TASK_FILE,
            Keys.ORIGIN,
            Keys.WITNESS_TRACE,
        ],
        rows=[
            [
                row.id,
                RunItemCategory.SUCCESS.value,
                row.status,
                row.seed,
                row.problem,
                _FIND_SOLUTION_ORIGIN,
                _artifact_relative(row.witness_trace, primary_format),
            ]
            for row in success_rows
        ],
    )
    def summary_row(
        row: _SolutionFailureRow | _SolutionSuccessRow,
    ) -> list[JsonValue]:
        category = (
            row.category
            if isinstance(row, _SolutionFailureRow)
            else RunItemCategory.SUCCESS.value
        )
        return [row.id, category, row.status, row.seed, row.problem]

    summary_rows = [summary_row(row) for row in failure_rows] + [
        summary_row(row) for row in success_rows
    ]
    artifacts[Keys.SUMMARY] = Table(
        name=Keys.SUMMARY,
        columns=[Keys.ID, Keys.CATEGORY, Keys.STATUS, Keys.SEED, Keys.TASK_FILE],
        rows=summary_rows,
    )

    paths = write_run(
        output_path,
        {
            **{f"dicts/{name}": table for name, table in dicts.tables().items()},
            **artifacts,
        },
        formats,
    )
    manifest: JsonObject = {
        Keys.SCHEMA_VERSION: 2,
        Keys.TOOL: _FIND_SOLUTION_TOOL,
        Keys.STATUS: result.status.value,
        Keys.CONTEXT: {Keys.ID: result.context.id, Keys.INDEX: result.context.index},
        **_candidate_metadata(result),
        Keys.CLASSIFIER_ID: result.classifier.id if result.classifier is not None else None,
        Keys.UNIVERSAL: result.universal,
        Keys.ROLLOUT_COUNT: result.num_rollouts,
        Keys.SEARCH_BUDGET: _budget_json(result.search_budget),
        Keys.PLAN_TRACE_BUDGET: _budget_json(result.plan_trace_budget),
        Keys.EVIDENCE: {
            Keys.WITNESS_TRACE: include_witness_trace,
            Keys.PLAN_TRACE: include_plan_trace,
            Keys.SUCCESSORS: include_successors,
        },
        Keys.ROLLOUTS: [
            {
                Keys.SEED: None if result.universal else seed,
                Keys.STATUS: status_name(proof.status),
                Keys.SUCCESSFUL: bool(proof.is_successful()),
            }
            for seed, proof in result.results
        ],
        Keys.ARTIFACTS: {
            Keys.SUMMARY: paths[Keys.SUMMARY],
            Keys.FAILURES: paths[Keys.FAILURES],
            Keys.SUCCESSES: paths[Keys.SUCCESSES],
        },
        Keys.FAILURES: [
            {
                Keys.ID: row.id,
                Keys.CATEGORY: row.category,
                Keys.STATUS: row.status,
                Keys.TASK_FILE: row.problem,
                Keys.SEED: row.seed,
                Keys.WITNESS_PATH: paths[row.witness],
                Keys.WITNESS_TRACE_PATH: paths[row.witness_trace] if row.witness_trace is not None else None,
                Keys.SUCCESSORS_PATH: paths[row.successors]
                if row.successors is not None
                else None,
                Keys.PLAN_TRACE_PATH: paths[row.plan_trace]
                if row.plan_trace is not None
                else None,
            }
            for row in failure_rows
        ],
        Keys.SUCCESSES: [
            {
                Keys.ID: row.id,
                Keys.CATEGORY: RunItemCategory.SUCCESS.value,
                Keys.STATUS: row.status,
                Keys.TASK_FILE: row.problem,
                Keys.SEED: row.seed,
                Keys.WITNESS_TRACE_PATH: paths[row.witness_trace],
            }
            for row in success_rows
        ],
        Keys.OUTPUT_DIR: output_path.resolve().as_posix(),
    }
    manifest_path = output_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return RichDumpResult(output_dir=output_path, primary_file=manifest_path)


def _dump_prove_classifier_artifacts(
    result: ProveClassifierResult, output_path: Path, formats: tuple[Fmt, ...]
) -> RichDumpResult | None:
    if not formats or not result.mistakes:
        return None
    dicts = Dictionaries(task=result.context.base_task.task_context.search_context.task, ext=False)
    feature_symbols = classifier_feature_symbols(result.candidate.value)
    for symbol in feature_symbols:
        dicts.feature(symbol)
    for kind, atom in result.atoms:
        dicts.atom(AtomKind(kind), atom)

    artifacts: dict[str, Artifact] = {}
    items: list[RunItem] = []
    for mistake in result.mistakes:
        category = RunItemCategory(mistake.category)
        row = ClassifierRow(
            id=mistake.id,
            category=category,
            state=mistake.state,
            features=mistake.features,
            fluent=mistake.fluent,
            derived=mistake.derived,
        )
        witness_name = f"failures/{mistake.id}/witness"
        artifacts[witness_name] = classifier_witness(
            row,
            feature_symbols,
            dicts,
            header=[
                (Keys.TOOL, result.kind.value),
                (Keys.ID, mistake.id),
                (Keys.CATEGORY, mistake.category),
                (Keys.SUBJECT, result.context.problem_file.name),
            ],
        )
        items.append(
            RunItem(
                id=mistake.id,
                category=category,
                subject=result.context.problem_file.name,
                witness=witness_name,
            )
        )

    envelope = build_run_envelope(
        tool=result.kind.value,
        status=RunStatus.FAILURE
        if result.status.value == RunStatus.FAILURE.value
        else RunStatus.SUCCESS,
        output_dir=output_path,
        metadata={**_candidate_metadata(result), Keys.COUNTS: _counts_json(result.counts)},
        dictionary_tables=dicts.tables(),
        artifacts=artifacts,
        items=items,
        category=RunCategory.COUNTEREXAMPLE,
        formats=formats,
    )
    output_dir = _output_dir_from_envelope(envelope, output_path)
    path = output_dir / "run.json"
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return RichDumpResult(output_dir=output_dir, primary_file=path)


def _policy_termination_vertices_edges(
    result: ProvePolicyTerminationResult,
) -> tuple[list[TerminationVertex], list[TerminationEdge]]:
    counterexample = result.policy_result.counterexample
    policy = result.candidate.value
    boolean_symbols = [feature_key(feature) for feature in policy.get_boolean_features()]
    numerical_symbols = [feature_key(feature) for feature in policy.get_numerical_features()]

    vertices: list[TerminationVertex] = []
    for index in counterexample.get_vertex_indices():
        vertex = counterexample.get_vertex_property(index)
        vertices.append(
            TerminationVertex(
                int(index),
                None,
                booleans={
                    symbol: "T" if value else "F"
                    for symbol, value in zip(
                        boolean_symbols, vertex.boolean_values, strict=True
                    )
                },
                numericals={
                    symbol: ">0" if value else "=0"
                    for symbol, value in zip(
                        numerical_symbols, vertex.numerical_values, strict=True
                    )
                },
            )
        )

    edges: list[TerminationEdge] = []
    for index in counterexample.get_edge_indices():
        edge = counterexample.get_edge_property(index)
        edges.append(
            TerminationEdge(
                int(index),
                int(counterexample.get_source(index)),
                int(counterexample.get_target(index)),
                edge.rule.get_symbol(),
                numerical_changes={
                    symbol: value.name.lower()
                    for symbol, value in zip(
                        numerical_symbols, edge.numerical_changes, strict=True
                    )
                },
            )
        )
    return vertices, edges

def _termination_vertices_edges(
    module_result: ModuleStructuralTerminationResult,
    module: Module,
) -> tuple[list[TerminationVertex], list[TerminationEdge]]:
    counterexample = module_result.counterexample
    boolean_symbols = [feature_key(feature) for feature in module.get_boolean_features()]
    numerical_symbols = [feature_key(feature) for feature in module.get_numerical_features()]

    vertices: list[TerminationVertex] = []
    for index in counterexample.get_vertex_indices():
        vertex = counterexample.get_vertex_property(index)
        vertices.append(
            TerminationVertex(
                int(index),
                vertex.memory_state.get_name(),
                booleans={
                    symbol: str(value)
                    for symbol, value in zip(
                        boolean_symbols, vertex.boolean_values, strict=True
                    )
                },
                numericals={
                    symbol: str(value)
                    for symbol, value in zip(
                        numerical_symbols, vertex.numerical_values, strict=True
                    )
                },
            )
        )

    edges: list[TerminationEdge] = []
    for index in counterexample.get_edge_indices():
        edge = counterexample.get_edge_property(index)
        edges.append(
            TerminationEdge(
                int(index),
                int(counterexample.get_source(index)),
                int(counterexample.get_target(index)),
                edge.rule.get_symbol(),
                numerical_changes={
                    symbol: str(value)
                    for symbol, value in zip(
                        numerical_symbols, edge.numerical_changes, strict=True
                    )
                },
            )
        )
    return vertices, edges


def _dump_prove_base_termination_artifacts(
    result: ProvePolicyTerminationResult,
    output_path: Path,
    formats: tuple[Fmt, ...],
) -> RichDumpResult | None:
    if not formats:
        return None
    dicts = TerminationDictionaries()
    artifacts: dict[str, Artifact] = {}
    items: list[RunItem] = []
    if not result.policy_result.is_terminating():
        item_id = "structural_termination-001"
        vertices, edges = _policy_termination_vertices_edges(result)
        witness_name = f"failures/{item_id}/witness"
        artifacts[witness_name] = termination_counterexample_document(
            header=[
                (Keys.TOOL, result.kind.value),
                (Keys.ID, item_id),
                (Keys.CATEGORY, "structural_termination"),
                (Keys.CANDIDATE_ID, result.candidate.id),
            ],
            vertices=vertices,
            edges=edges,
            dicts=dicts,
            include_memory=False,
        )
        items.append(
            RunItem(
                id=item_id,
                category=RunItemCategory.STRUCTURAL_TERMINATION,
                subject=result.candidate.id,
                witness=witness_name,
            )
        )
    envelope = build_run_envelope(
        tool="runir.ps.base.prove_termination",
        status=RunStatus.SUCCESS
        if result.status.value == RunStatus.SUCCESS.value
        else RunStatus.FAILURE,
        output_dir=output_path,
        metadata={
            **_candidate_metadata(result),
            Keys.PROGRAM_STATUS: result.policy_result.status.name.lower(),
            Keys.INCOMPLETE_TERMINATION_STATUS: result.incomplete_termination_status.value,
        },
        dictionary_tables=dicts.tables(include_memory=False),
        artifacts=artifacts,
        items=items,
        category=RunCategory.SUCCESS
        if result.status.value == RunStatus.SUCCESS.value
        else RunCategory.COUNTEREXAMPLE,
        formats=formats,
    )
    output_dir = _output_dir_from_envelope(envelope, output_path)
    path = output_dir / "run.json"
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return RichDumpResult(output_dir=output_dir, primary_file=path)

def _dump_prove_termination_artifacts(
    result: ProveTerminationResult, output_path: Path, formats: tuple[Fmt, ...]
) -> RichDumpResult | None:
    if not formats:
        return None
    dicts = TerminationDictionaries()
    artifacts: dict[str, Artifact] = {}
    items: list[RunItem] = []
    modules = result.candidate.value.get_modules()
    for index, module_result in enumerate(result.program_result.module_results):
        if module_result.is_terminating():
            continue
        if index >= len(modules):
            raise ValueError("termination result/module count mismatch")
        module = modules[index]
        module_name = module.get_name()
        item_id = f"structural_termination-{len(items) + 1:03d}"
        vertices, edges = _termination_vertices_edges(module_result, module)
        witness_name = f"failures/{item_id}/witness"
        artifacts[witness_name] = termination_counterexample_document(
            header=[
                (Keys.TOOL, result.kind.value),
                (Keys.ID, item_id),
                (Keys.CATEGORY, "structural_termination"),
                (Keys.MODULE, module_name),
            ],
            vertices=vertices,
            edges=edges,
            dicts=dicts,
        )
        items.append(
            RunItem(
                id=item_id,
                category=RunItemCategory.STRUCTURAL_TERMINATION,
                subject=module_name,
                witness=witness_name,
            )
        )
    envelope = build_run_envelope(
        tool="runir.ps.ext.prove_termination",
        status=RunStatus.SUCCESS
        if result.status.value == RunStatus.SUCCESS.value
        else RunStatus.FAILURE,
        output_dir=output_path,
        metadata={
            **_candidate_metadata(result),
            Keys.PROGRAM_STATUS: result.program_result.status.name.lower(),
            Keys.INCOMPLETE_TERMINATION_STATUS: result.incomplete_termination_status.value,
            Keys.NONTERMINATING_MODULES: list(result.nonterminating_modules),
        },
        dictionary_tables=dicts.tables(),
        artifacts=artifacts,
        items=items,
        category=RunCategory.SUCCESS
        if result.status.value == RunStatus.SUCCESS.value
        else RunCategory.COUNTEREXAMPLE,
        formats=formats,
    )
    output_dir = _output_dir_from_envelope(envelope, output_path)
    path = output_dir / "run.json"
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return RichDumpResult(output_dir=output_dir, primary_file=path)


def _dump_rich_artifacts(
    result: ValidationResult,
    output_path: Path,
    formats: tuple[Fmt, ...],
    *,
    include_witness_trace: bool,
    include_plan_trace: bool,
    include_successors: bool,
) -> RichDumpResult | None:
    if isinstance(result, (FindPolicySolutionResult, FindModuleProgramSolutionResult)):
        return _dump_solution_artifacts(
            result,
            output_path,
            formats,
            include_witness_trace=include_witness_trace,
            include_plan_trace=include_plan_trace,
            include_successors=include_successors,
        )
    if isinstance(result, ProveClassifierResult):
        return _dump_prove_classifier_artifacts(result, output_path, formats)
    if isinstance(result, ProvePolicyTerminationResult):
        return _dump_prove_base_termination_artifacts(result, output_path, formats)
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
    section: str | None = None
    id_column: int | None = None
    module_column: int | None = None
    memory_column: int | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("@"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            id_column = None
            continue
        if section != Keys.STATES:
            continue
        parts = [part.strip() for part in line.split("|")]
        if id_column is None:
            if TableColumns.STATE_ID in parts:
                id_column = parts.index(TableColumns.STATE_ID)
            module_column = (
                parts.index(TableColumns.MODULE_ID) if TableColumns.MODULE_ID in parts else None
            )
            memory_column = (
                parts.index(TableColumns.MEMORY_ID) if TableColumns.MEMORY_ID in parts else None
            )
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
    return None, tuple(ids)


def solution_observation_from_manifest(
    result: ValidationResult, manifest_path: Path | None
) -> ValidationObservation:
    if not isinstance(result, (FindPolicySolutionResult, FindModuleProgramSolutionResult)):
        return result.observation
    if manifest_path is None or not manifest_path.exists():
        return result.observation
    manifest = cast(JsonObject, json.loads(manifest_path.read_text(encoding="utf-8")))
    failures = manifest.get(Keys.FAILURES)
    if not isinstance(failures, list) or not failures:
        return result.observation
    failure = failures[0]
    if not isinstance(failure, dict):
        return result.observation
    category = failure.get(Keys.CATEGORY)
    problem_file = failure.get(Keys.TASK_FILE)
    if not isinstance(category, str):
        return result.observation
    witness_ids: tuple[str, ...] = ()
    witness_path = failure.get(Keys.WITNESS_PATH)
    if isinstance(witness_path, str):
        category_override, witness_ids = _witness_info_from_file(Path(witness_path))
        if category_override is not None:
            category = category_override
        if category == CounterexampleKind.CYCLE:
            witness_ids = rotate_smallest_state_id_first(witness_ids)
    fingerprint = FailureFingerprint(
        kind=result.kind,
        status=result.status,
        problem_file=problem_file if isinstance(problem_file, str) else None,
        category=category,
        witness=witness_ids,
    )
    return replace(result.observation, fingerprint=fingerprint)


def _dump_task_generation_result(
    result: TaskGenerationResult,
    output_dir: str | Path,
    *,
    formats: tuple[DumpFormat, ...],
) -> DumpResult:
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    if DumpFormat.JSON in formats:
        path = output_path / "result.json"
        path.write_text(
            json.dumps(task_generation_json(result), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files.append(path)
    if DumpFormat.MD in formats:
        path = output_path / "summary.md"
        write_task_generation_markdown(path, result)
        files.append(path)
    return DumpResult(output_dir=output_path, files=tuple(files))


def dump_result(
    result: ValidationResult | TaskGenerationResult,
    output_dir: str | Path,
    *,
    formats: tuple[DumpFormat, ...] = (DumpFormat.JSON,),
    include_witness_trace: bool = True,
    include_plan_trace: bool = True,
    include_successors: bool = True,
) -> DumpResult:
    if isinstance(result, TaskGenerationResult):
        return _dump_task_generation_result(result, output_dir, formats=formats)

    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []

    rich_formats = _render_formats(formats)
    rich_dump = _dump_rich_artifacts(
        result,
        output_path,
        rich_formats,
        include_witness_trace=include_witness_trace,
        include_plan_trace=include_plan_trace,
        include_successors=include_successors,
    )
    actual_output_dir = rich_dump.output_dir if rich_dump is not None else output_path
    if rich_dump is not None:
        files.append(rich_dump.primary_file)
    observation = solution_observation_from_manifest(
        result, rich_dump.primary_file if rich_dump is not None else None
    )

    # Always keep the compact machine-readable sidecar; callers use it for state/history plumbing.
    path = actual_output_dir / "result.json"
    path.write_text(
        json.dumps(_result_json(result, observation=observation), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    files.append(path)
    return DumpResult(output_dir=actual_output_dir, files=tuple(files))


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
            Keys.OBSERVATIONS: [
                _observation_json(observation) for observation in history.observations
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files.append(path)
    return DumpResult(output_dir=output_path, files=tuple(files))
