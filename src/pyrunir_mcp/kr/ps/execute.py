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

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.frontier import FrontierExpander
from pyrunir_mcp.kr.ps.proof import (
    CounterexampleKind,
    ProofResult,
    StateEvidence,
    failure_items,
    is_goal_open_state_result,
    successful_trace_artifact,
    witness_artifacts,
)
from pyrunir_mcp.kr.ps.status import AnyStatus, SuccessStatus, is_success_status
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.run import FailureCategory, RunCategory, RunItemCategory, status_category
from pyrunir_mcp.output.writer import Artifact, resolve_formats, write_run
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
    return status_category(str(result.status.name)), None  # e.g. resource_limit (no graph witness)


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


def _write_success_meta(output_dir: Path, success: _SuccessTrace, source: str, primary: str) -> str:
    meta = {
        "id": success.id,
        "category": success.category.value,
        "status": success.status.value,
        "seed": success.seed,
        "problem": success.problem,
        "source": source,
        "files": {"trace": f"trace.{primary}"},
    }
    path = output_dir / "successes" / success.id / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path.resolve().as_posix()


def _write_failure_meta(output_dir: Path, rep: _Representative, source: str, primary: str) -> str:
    """Write `failures/<id>/meta.json` (the failure's row fields + the artifact filenames present in
    its directory) and return its absolute path. Always JSON, regardless of the render formats."""
    files = {
        label: f"{label}.{primary}"
        for label, name in (
            ("witness", rep.witness),
            ("trace", rep.trace),
            ("successors", rep.successors),
        )
        if name is not None
    }
    meta = {
        "id": rep.id,
        "category": rep.category.value,
        "status": rep.status.name,
        "seed": rep.seed,
        "problem": rep.problem,
        "source": source,
        "files": files,
    }
    path = output_dir / "failures" / rep.id / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path.resolve().as_posix()


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
    formats: tuple[Fmt, ...] | None = None,
) -> tuple[Task, ProofResult] | None:
    """Run rollouts and write the new-format artifacts. Returns the first failing (task, result)."""
    rollouts: list[JsonObject] = []
    task_rows: list[JsonObject] = []
    representatives: dict[
        tuple[str, str], tuple[int, Task, ProofResult, int | list[int] | None]
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
                failure_category = None
            elif isinstance(kind, CounterexampleKind):
                failure_category = RunItemCategory(kind.value)
            else:
                failure_category = kind
            category_value = failure_category.value if failure_category is not None else None
            task_rows.append(
                {
                    "problem_file": task.problem_path.name,
                    "status": SuccessStatus.SUCCESS.value
                    if effective_success
                    else str(result.status.name),
                    "failure_category": category_value,
                    "seed": seed,
                }
            )
            if effective_success:
                successful_runs.append((seed, task, result))
            if not effective_success:
                seed_failed, seed_category = True, category_value
                if first_failure is None:
                    first_failure = (task, result)
                if failure_category is not None and category_value is not None:
                    representatives.setdefault(
                        (task.problem_path.name, category_value), (seed, task, result, witness)
                    )
        rollouts.append(
            {
                "seed": seed,
                "status": "FAILURE" if seed_failed else SuccessStatus.SUCCESS.value,
                "failure_category": seed_category,
                "executed_tasks": len(tasks),
            }
        )

    # Everything for one failure is local to `failures/<id>/`; <id> already encodes the category.
    artifacts: dict[str, Artifact] = {}
    reps: list[_Representative] = []
    for index, ((problem, category_value), (seed, task, result, witness)) in enumerate(
        representatives.items(), start=1
    ):
        category: FailureCategory = (
            RunItemCategory(category_value)
            if category_value in RunItemCategory._value2member_map_
            else RunCategory(category_value)
        )
        failure_id = f"{category.value}-{index:03d}"
        names: dict[str, str | None] = {"witness": None, "trace": None, "successors": None}
        if witness is not None:
            header = [
                ("tool", tool),
                ("id", failure_id),
                ("category", category.value),
                ("status", result.status.name),
                ("problem", problem),
                ("seed", str(seed)),
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
                                (key, value if key != "id" else failure_id) for key, value in header
                            ]
                            header = [
                                (key, value if key != "category" else category.value)
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
            names["witness"] = f"failures/{failure_id}/witness"
            artifacts[names["witness"]] = witness_doc
            if trace is not None:
                names["trace"] = f"failures/{failure_id}/trace"
                artifacts[names["trace"]] = trace
            if successors is not None:
                names["successors"] = f"failures/{failure_id}/successors"
                artifacts[names["successors"]] = successors
        reps.append(
            _Representative(
                failure_id,
                category,
                result.status,
                seed,
                problem,
                names["witness"],
                names["trace"],
                names["successors"],
            )
        )

    successes: list[_SuccessTrace] = []
    for index, (seed, task, result) in enumerate(successful_runs, start=1):
        success_id = f"success-{index:03d}"
        problem = task.problem_path.name
        trace_name = f"successes/{success_id}/trace"
        header = [
            ("tool", tool),
            ("id", success_id),
            ("category", RunItemCategory.SUCCESS.value),
            ("status", SuccessStatus.SUCCESS.value),
            ("problem", problem),
            ("seed", str(seed)),
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

    artifacts["failures"] = Table(
        name="failures",
        columns=[
            "id",
            "category",
            "status",
            "seed",
            "problem",
            "source",
            "trace",
            "witness",
            "successors",
        ],
        rows=[
            [
                r.id,
                r.category.value,
                r.status.name,
                r.seed,
                r.problem,
                "find_solution",
                _relative(r.trace),
                _relative(r.witness),
                _relative(r.successors),
            ]
            for r in reps
        ],
    )
    artifacts["successes"] = Table(
        name="successes",
        columns=["id", "category", "status", "seed", "problem", "source", "trace"],
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
    artifacts["summary"] = Table(
        name="summary",
        columns=["id", "category", "status", "seed", "problem"],
        rows=[[r.id, r.category.value, str(r.status.name), r.seed, r.problem] for r in reps],
    )

    paths = write_run(
        output_dir,
        {**{f"dicts/{name}": table for name, table in dicts.tables().items()}, **artifacts},
        formats,
    )
    primary = resolve_formats(formats)[0]
    meta_paths = {r.id: _write_failure_meta(output_dir, r, "find_solution", primary) for r in reps}
    success_meta_paths = {
        s.id: _write_success_meta(output_dir, s, "find_solution", primary) for s in successes
    }

    manifest = {
        "tool": tool,
        **manifest_metadata,
        "status": SuccessStatus.SUCCESS.value if first_failure is None else "FAILURE",
        "rollouts": rollouts,
        "tasks": task_rows,
        "distinct_failures": [
            {
                "id": r.id,
                "failure_category": r.category.value,
                "problem_file": r.problem,
                "seed": r.seed,
                "witness_path": paths.get(r.witness) if r.witness is not None else None,
                "trace_path": paths.get(r.trace) if r.trace is not None else None,
                "successors_path": paths.get(r.successors) if r.successors is not None else None,
                "meta_path": meta_paths[r.id],
                "trace_available": r.trace is not None,
            }
            for r in reps
        ],
        "successful_traces": [
            {
                "id": s.id,
                "category": s.category.value,
                "problem_file": s.problem,
                "seed": s.seed,
                "trace_path": paths.get(s.trace),
                "meta_path": success_meta_paths[s.id],
                "trace_available": True,
            }
            for s in successes
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return first_failure
