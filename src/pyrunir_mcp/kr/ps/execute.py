"""Shared execute-policy orchestration for the base and module-program tools.

Both run rollouts, dedup the first failure per (task, category), extract each representative
witness from its result graph (reusing `proof.witness_artifacts` — same tyr repository, so
indices stay consistent), and write the dictionaries + witness files + `failures`/`summary`
tables + `manifest.json`. Each tool supplies only the family-specific bits: how to solve a
rollout, the policy features/rules, and the manifest's source-file metadata.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Protocol, TypeAlias, overload

from pyrunir.datasets import GroundTaskSearchContext
from pyrunir.kr.ps.base import GroundSketchSearchOptions
from pyrunir.kr.ps.ext import GroundModuleProgramSearchOptions
from pytyr.planning.ground import State as GroundState

from pyrunir_mcp.enums import CounterexampleKind, RunCategory, RunItemCategory, RunStatus, SuccessStatus
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.keys import (
    Keys,
)
from pyrunir_mcp.kr.ps.frontier import FrontierExpander
from pyrunir_mcp.kr.ps.proof import (
    ProofResult,
    StateEvidence,
    failure_items,
    is_goal_open_state_result,
    successful_trace_artifact,
    witness_artifacts,
    witness_ground_state,
)
from pyrunir_mcp.kr.ps.status import AnyStatus, is_success_status
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.run import status_category
from pyrunir_mcp.output.writer import Artifact, write_run
from pyrunir_mcp.tables import Document, Fmt, Table

RolloutFallbackResult = (
    tuple[Document, Document | None, Document | None]
    | tuple[Document, Document | None, Document | None, str | None]
    | None
)


class RolloutFallback(Protocol):
    def __call__(
        self,
        task: "Task",
        *,
        header: list[tuple[str, str]],
        evidence: StateEvidence,
        feature_symbols: list[str],
        dicts: Dictionaries,
    ) -> RolloutFallbackResult: ...


SearchOptions: TypeAlias = GroundSketchSearchOptions | GroundModuleProgramSearchOptions
FailureCategory: TypeAlias = RunCategory | RunItemCategory


class Task(Protocol):
    @property
    def problem_path(self) -> Path: ...

    @property
    def search_context(self) -> GroundTaskSearchContext: ...


def rollout_seeds(num_rollouts: int, random_seed: int, random_seed_start: int) -> list[int]:
    if num_rollouts == 1:
        return [random_seed]
    return [random_seed_start + offset for offset in range(num_rollouts)]


@overload
def configure_search_options(
    search_options: GroundSketchSearchOptions,
    *,
    random_seed: int,
    shuffle_labeled_succ_nodes: bool,
    max_arity: int = 0,
    max_num_states: int | None = None,
    max_time_seconds: float | None = None,
) -> GroundSketchSearchOptions: ...


@overload
def configure_search_options(
    search_options: GroundModuleProgramSearchOptions,
    *,
    random_seed: int,
    shuffle_labeled_succ_nodes: bool,
    max_arity: int = 0,
    max_num_states: int | None = None,
    max_time_seconds: float | None = None,
) -> GroundModuleProgramSearchOptions: ...


def configure_search_options(
    search_options: SearchOptions,
    *,
    random_seed: int,
    shuffle_labeled_succ_nodes: bool,
    max_arity: int = 0,
    max_num_states: int | None = None,
    max_time_seconds: float | None = None,
) -> SearchOptions:
    """Apply the shared base/ext greedy-execution knobs onto a family-specific options object
    (both expose `brfs_options` and `max_arity`)."""
    search_options.brfs_options.random_seed = random_seed
    search_options.brfs_options.shuffle_labeled_succ_nodes = shuffle_labeled_succ_nodes
    search_options.max_arity = max_arity
    if max_num_states is not None:
        search_options.brfs_options.max_num_states = max_num_states
    if max_time_seconds is not None:
        search_options.brfs_options.max_time = timedelta(seconds=max_time_seconds)
    return search_options


def _result_failure(
    result: ProofResult, evidence: StateEvidence | None
) -> tuple[CounterexampleKind | RunCategory | None, int | list[int] | None]:
    """The failure category and graph witness for a rollout result (None when it succeeded)."""
    items = failure_items(
        result,
        max_open_state_counterexamples=1,
        max_deadend_transition_counterexamples=1,
        evidence=evidence,
    )
    if items:
        return items[0]
    if is_success_status(result.status):
        return None, None
    return status_category(result.status.name), None  # e.g. out_of_states (no graph witness)


@dataclass(frozen=True)
class _Representative:
    id: str
    category: FailureCategory
    status: AnyStatus
    seed: int
    problem: str
    witness: str | None
    trace: str | None
    successors: str | None
    plan_trace: str | None


@dataclass(frozen=True)
class _SuccessTrace:
    id: str
    category: FailureCategory
    status: AnyStatus
    seed: int
    problem: str
    trace: str


def _relative(name: str | None) -> str:
    return f"{name}.psv" if name else ""


def _with_header(doc: Document | None, header: list[tuple[str, str]]) -> Document | None:
    if doc is None:
        return None
    return Document(header=list(header), sections=doc.sections)


def with_docs_header(
    docs: tuple[Document, Document | None, Document | None], header: list[tuple[str, str]]
) -> tuple[Document, Document | None, Document | None]:
    return (
        Document(header=list(header), sections=docs[0].sections),
        _with_header(docs[1], header),
        _with_header(docs[2], header),
    )


def run_execute(
    *,
    tool: str,
    ext: bool,
    output_dir: Path,
    seeds: list[int],
    tasks: list[Task],
    solve: Callable[[Task, int], ProofResult],
    feature_symbols: list[str],
    evidence: StateEvidence,
    dicts: Dictionaries,
    manifest_metadata: JsonObject,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
    expander_factory: Callable[[Task], FrontierExpander] | None = None,
    rollout_fallback: RolloutFallback | None = None,
    open_state_plan: Callable[[Task, GroundState], Document | None] | None = None,
    formats: tuple[Fmt, ...] | None = None,
) -> tuple[Task, ProofResult] | None:
    """Run rollouts and write the new-format artifacts. Returns the first failing (task, result)."""
    rollouts: list[JsonObject] = []
    task_rows: list[JsonObject] = []
    representatives: dict[
        tuple[str, str, int], tuple[int, Task, ProofResult, int | list[int] | None]
    ] = {}
    successful_runs: list[tuple[int, Task, ProofResult]] = []
    first_failure: tuple[Task, ProofResult] | None = None

    for seed in seeds:
        seed_failed = False
        seed_category: str | None = None
        for task in tasks:
            result = solve(task, seed)
            effective_success = is_success_status(result.status) or is_goal_open_state_result(
                result
            )
            kind, witness = (
                _result_failure(result, evidence) if not effective_success else (None, None)
            )
            if kind is None:
                item_category = None
            elif isinstance(kind, CounterexampleKind):
                item_category = RunItemCategory(kind.value)
            else:
                item_category = kind
            category_value = item_category.value if item_category is not None else None
            task_rows.append(
                {
                    Keys.TASK_FILE: task.problem_path.name,
                    Keys.STATUS: SuccessStatus.SUCCESS.value
                    if effective_success
                    else result.status.name.lower(),
                    Keys.CATEGORY: category_value,
                    Keys.SEED: seed,
                }
            )
            if effective_success:
                successful_runs.append((seed, task, result))
            if not effective_success:
                seed_failed, seed_category = True, category_value
                if first_failure is None:
                    first_failure = (task, result)
                if item_category is not None and category_value is not None:
                    representatives.setdefault(
                        (task.problem_path.name, category_value, seed), (seed, task, result, witness)
                    )
        rollouts.append(
            {
                Keys.SEED: seed,
                Keys.STATUS: RunStatus.FAILURE.value if seed_failed else RunStatus.SUCCESS.value,
                Keys.CATEGORY: seed_category,
            }
        )

    # Everything for one failure is local to `failures/<id>/`; <id> already encodes the category.
    artifacts: dict[str, Artifact] = {}
    reps: list[_Representative] = []
    for index, ((problem, category_value, _seed_key), (seed, task, result, witness)) in enumerate(
        representatives.items(), start=1
    ):
        category: FailureCategory = (
            RunItemCategory(category_value)
            if category_value in RunItemCategory._value2member_map_
            else RunCategory(category_value)
        )
        failure_id = f"{category.value}-{index:03d}"
        names: dict[str, str | None] = {Keys.WITNESS: None, Keys.TRACE: None, Keys.SUCCESSORS: None, Keys.PLAN_TRACE: None}
        if witness is not None:
            header: list[tuple[str, str]] = [
                (Keys.TOOL, tool),
                (Keys.ID, failure_id),
                (Keys.CATEGORY, category.value),
                (Keys.STATUS, result.status.name.lower()),
                (Keys.TASK_FILE, problem),
                (Keys.SEED, str(seed)),
            ]
            # Base greedy `find_solution` reports a single init vertex on a downstream failure
            # (the committed prefix is discarded upstream). When that happens, roll the policy forward
            # in Python to surface the real stuck state instead of the misleading init witness.
            docs: tuple[Document, Document | None, Document | None] | None = None
            kind = (
                CounterexampleKind(category.value)
                if category.value in CounterexampleKind._value2member_map_
                else None
            )
            if (
                rollout_fallback is not None
                and kind == CounterexampleKind.OPEN_STATE
                and result.graph.get_num_vertices() == 1
            ):
                fallback = rollout_fallback(
                    task,
                    header=header,
                    evidence=evidence,
                    feature_symbols=feature_symbols,
                    dicts=dicts,
                )
                if fallback is not None:
                    if len(fallback) == 4:
                        docs = (fallback[0], fallback[1], fallback[2])
                        if fallback[3] is not None:
                            category = RunItemCategory(str(fallback[3]))
                            kind = (
                                CounterexampleKind(category.value)
                                if category.value in CounterexampleKind._value2member_map_
                                else None
                            )
                            failure_id = f"{category.value}-{index:03d}"
                            header = [
                                (key, value if key != Keys.ID else failure_id) for key, value in header
                            ]
                            header = [
                                (key, value if key != Keys.CATEGORY else category.value)
                                for key, value in header
                            ]
                            docs = with_docs_header(docs, header)
                    else:
                        docs = fallback
            if docs is None:
                if kind is None:
                    raise RuntimeError(
                        f"Cannot build witness artifacts for non-counterexample category: {category.value}"
                    )
                expander = expander_factory(task) if expander_factory is not None else None
                docs = witness_artifacts(
                    result.graph,
                    kind,
                    witness,
                    evidence,
                    feature_symbols=feature_symbols,
                    dicts=dicts,
                    ext=ext,
                    header=header,
                    expander=expander,
                    include_hstar=include_hstar,
                    include_hlmcut=include_hlmcut,
                )
            witness_doc, trace, successors = docs
            plan_trace = None
            if kind == CounterexampleKind.OPEN_STATE and open_state_plan is not None:
                plan_trace = open_state_plan(task, witness_ground_state(result.graph, witness))
                if plan_trace is not None:
                    plan_trace = Document(header=[*header, (Keys.ORIGIN, "ff")], sections=plan_trace.sections)
            witness_name = f"failures/{failure_id}/witness"
            names[Keys.WITNESS] = witness_name
            artifacts[witness_name] = witness_doc
            if trace is not None:
                trace_name = f"failures/{failure_id}/trace"
                names[Keys.TRACE] = trace_name
                artifacts[trace_name] = trace
            if successors is not None:
                successors_name = f"failures/{failure_id}/successors"
                names[Keys.SUCCESSORS] = successors_name
                artifacts[successors_name] = successors
            if plan_trace is not None:
                plan_trace_name = f"failures/{failure_id}/plan_trace"
                names[Keys.PLAN_TRACE] = plan_trace_name
                artifacts[plan_trace_name] = plan_trace
        reps.append(
            _Representative(
                failure_id,
                category,
                result.status,
                seed,
                problem,
                names[Keys.WITNESS],
                names[Keys.TRACE],
                names[Keys.SUCCESSORS],
                names[Keys.PLAN_TRACE],
            )
        )

    successes: list[_SuccessTrace] = []
    for index, (seed, task, result) in enumerate(successful_runs, start=1):
        success_id = f"success-{index:03d}"
        problem = task.problem_path.name
        trace_name = f"successes/{success_id}/trace"
        header: list[tuple[str, str]] = [
            (Keys.TOOL, tool),
            (Keys.ID, success_id),
            (Keys.CATEGORY, RunItemCategory.SUCCESS.value),
            (Keys.STATUS, SuccessStatus.SUCCESS.value),
            (Keys.TASK_FILE, problem),
            (Keys.SEED, str(seed)),
        ]
        trace = successful_trace_artifact(
            result.graph,
            evidence,
            feature_symbols=feature_symbols,
            dicts=dicts,
            ext=ext,
            header=header,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        if trace is None:
            continue
        artifacts[trace_name] = trace
        successes.append(
            _SuccessTrace(
                success_id,
                RunItemCategory.SUCCESS,
                SuccessStatus.SUCCESS,
                seed,
                problem,
                trace_name,
            )
        )

    artifacts[Keys.FAILURES] = Table(
        name="failures",
        columns=[
            Keys.ID,
            Keys.CATEGORY,
            Keys.STATUS,
            Keys.SEED,
            Keys.TASK_FILE,
            Keys.ORIGIN,
            Keys.TRACE,
            Keys.WITNESS,
            Keys.SUCCESSORS,
            Keys.PLAN_TRACE,
        ],
        rows=[
            [
                r.id,
                r.category.value,
                r.status.name.lower(),
                r.seed,
                r.problem,
                "find_solution",
                _relative(r.trace),
                _relative(r.witness),
                _relative(r.successors),
                _relative(r.plan_trace),
            ]
            for r in reps
        ],
    )
    artifacts[Keys.SUCCESSES] = Table(
        name="successes",
        columns=[Keys.ID, Keys.CATEGORY, Keys.STATUS, Keys.SEED, Keys.TASK_FILE, Keys.ORIGIN, Keys.TRACE],
        rows=[
            [
                s.id,
                s.category.value,
                s.status.value,
                s.seed,
                s.problem,
                "find_solution",
                _relative(s.trace),
            ]
            for s in successes
        ],
    )
    artifacts[Keys.SUMMARY] = Table(
        name=Keys.SUMMARY,
        columns=[Keys.ID, Keys.CATEGORY, Keys.STATUS, Keys.SEED, Keys.TASK_FILE],
        rows=[[r.id, r.category.value, r.status.name.lower(), r.seed, r.problem] for r in reps],
    )

    paths = write_run(
        output_dir,
        {**{f"dicts/{name}": table for name, table in dicts.tables().items()}, **artifacts},
        formats,
    )

    manifest = {
        Keys.TOOL: tool,
        **manifest_metadata,
        Keys.STATUS: RunStatus.SUCCESS.value if first_failure is None else RunStatus.FAILURE.value,
        Keys.ROLLOUTS: rollouts,
        Keys.TASKS: task_rows,
        Keys.FAILURES: [
            {
                Keys.ID: r.id,
                Keys.CATEGORY: r.category.value,
                Keys.TASK_FILE: r.problem,
                Keys.SEED: r.seed,
                Keys.WITNESS_PATH: paths.get(r.witness) if r.witness is not None else None,
                Keys.TRACE_PATH: paths.get(r.trace) if r.trace is not None else None,
                Keys.SUCCESSORS_PATH: paths.get(r.successors) if r.successors is not None else None,
                Keys.PLAN_TRACE_PATH: paths.get(r.plan_trace) if r.plan_trace is not None else None,
            }
            for r in reps
        ],
        Keys.SUCCESSES: [
            {
                Keys.ID: s.id,
                Keys.CATEGORY: s.category.value,
                Keys.TASK_FILE: s.problem,
                Keys.SEED: s.seed,
                Keys.TRACE_PATH: paths.get(s.trace),
            }
            for s in successes
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return first_failure
