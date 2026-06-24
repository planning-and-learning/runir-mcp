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
from typing import Protocol, TypeVar

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.frontier import FrontierExpander
from pyrunir_mcp.kr.ps.proof import ProofResult, StateEvidence, failure_items, witness_artifacts
from pyrunir_mcp.kr.ps.status import is_success_status
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.writer import Artifact, resolve_formats, write_run
from pyrunir_mcp.tables import Document, Table

# Produce (counterexample, trace, successors) docs for a base init-only open-state failure, or None to
# fall back to the default graph witness. Keyword args mirror what `witness_artifacts` consumes.
RolloutFallback = Callable[..., tuple[Document, Document | None, Document | None] | None]

SearchOptions = TypeVar("SearchOptions")


class Task(Protocol):
    @property
    def problem_path(self) -> Path: ...


def rollout_seeds(num_rollouts: int, random_seed: int, random_seed_start: int) -> list[int]:
    if num_rollouts == 1:
        return [random_seed]
    return [random_seed_start + offset for offset in range(num_rollouts)]


def configure_search_options(
    search_options: SearchOptions,
    *,
    random_seed: int,
    shuffle_labeled_succ_nodes: bool,
    max_arity: int,
    max_num_states: int | None,
    max_time_seconds: float | None,
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


def _result_failure(result: ProofResult) -> tuple[str | None, int | list[int] | None]:
    """The failure category and graph witness for a rollout result (None when it succeeded)."""
    items = failure_items(result, max_open_state_counterexamples=1, max_deadend_transition_counterexamples=1)
    if items:
        return items[0]
    if is_success_status(result.status):
        return None, None
    return result.status.name.lower(), None  # e.g. resource_limit (no graph witness)


@dataclass(frozen=True)
class _Representative:
    id: str
    category: str
    status: str
    seed: int
    problem: str
    witness: str | None
    trace: str | None
    successors: str | None


def _relative(name: str | None) -> str:
    return f"{name}.psv" if name else ""


def _write_failure_meta(output_dir: Path, rep: _Representative, source: str) -> str:
    """Write `failures/<id>/meta.json` (the failure's row fields + the artifact filenames present in
    its directory) and return its absolute path. Always JSON, regardless of the render formats."""
    primary = resolve_formats()[0]
    files = {
        label: f"{label}.{primary}"
        for label, name in (("witness", rep.witness), ("trace", rep.trace), ("successors", rep.successors))
        if name is not None
    }
    meta = {
        "id": rep.id,
        "category": rep.category,
        "status": rep.status,
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
    expander_factory: Callable[[Task], FrontierExpander] | None = None,
    rollout_fallback: RolloutFallback | None = None,
) -> tuple[Task, ProofResult] | None:
    """Run rollouts and write the new-format artifacts. Returns the first failing (task, result)."""
    rollouts: list[JsonObject] = []
    task_rows: list[JsonObject] = []
    representatives: dict[tuple[str, str], tuple[int, Task, ProofResult, int | list[int] | None]] = {}
    first_failure: tuple[Task, ProofResult] | None = None

    for seed in seeds:
        seed_failed, seed_category = False, None
        for index, task in enumerate(tasks, start=1):
            result = solve(task, seed)
            print(f"[seed {seed}] [{index}/{len(tasks)}] {task.problem_path.name}: {result.status.name}", flush=True)
            category, witness = _result_failure(result)
            task_rows.append({"problem_file": task.problem_path.name, "status": result.status.name, "failure_category": category, "seed": seed})
            if not is_success_status(result.status):
                seed_failed, seed_category = True, category
                if first_failure is None:
                    first_failure = (task, result)
                if category is not None:
                    representatives.setdefault((task.problem_path.name, category), (seed, task, result, witness))
        rollouts.append({"seed": seed, "status": "FAILURE" if seed_failed else "SUCCESS", "failure_category": seed_category, "executed_tasks": len(tasks)})

    # Everything for one failure is local to `failures/<id>/`; <id> already encodes the category.
    artifacts: dict[str, Artifact] = {}
    reps: list[_Representative] = []
    for index, ((problem, category), (seed, task, result, witness)) in enumerate(representatives.items(), start=1):
        failure_id = f"{category}-{index:03d}"
        names: dict[str, str | None] = {"witness": None, "trace": None, "successors": None}
        if witness is not None:
            header = [("tool", tool), ("id", failure_id), ("category", category), ("status", result.status.name), ("problem", problem), ("seed", str(seed))]
            # Base greedy `find_ground_solution` reports a single init vertex on a downstream failure
            # (the committed prefix is discarded upstream). When that happens, roll the policy forward
            # in Python to surface the real stuck state instead of the misleading init witness.
            docs: tuple[Document, Document | None, Document | None] | None = None
            if rollout_fallback is not None and category == "open_state" and result.graph.get_num_vertices() == 1:
                docs = rollout_fallback(task, header=header, evidence=evidence, feature_symbols=feature_symbols, dicts=dicts)
            if docs is None:
                expander = expander_factory(task) if expander_factory is not None else None
                docs = witness_artifacts(
                    result.graph, category, witness, evidence, feature_symbols=feature_symbols, dicts=dicts, ext=ext, header=header, expander=expander
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
        reps.append(_Representative(failure_id, category, result.status.name, seed, problem, names["witness"], names["trace"], names["successors"]))

    artifacts["failures"] = Table(
        name="failures",
        columns=["id", "category", "status", "seed", "problem", "source", "trace", "witness", "successors"],
        rows=[[r.id, r.category, r.status, r.seed, r.problem, "find_ground_solution", _relative(r.trace), _relative(r.witness), _relative(r.successors)] for r in reps],
    )
    artifacts["summary"] = Table(name="summary", columns=["id", "category", "status", "seed", "problem"], rows=[[r.id, r.category, r.status, r.seed, r.problem] for r in reps])

    paths = write_run(output_dir, {**{f"dicts/{name}": table for name, table in dicts.tables().items()}, **artifacts})
    meta_paths = {r.id: _write_failure_meta(output_dir, r, "find_ground_solution") for r in reps}

    manifest = {
        "tool": tool,
        **manifest_metadata,
        "status": "SUCCESS" if first_failure is None else "FAILURE",
        "rollouts": rollouts,
        "tasks": task_rows,
        "distinct_failures": [
            {
                "id": r.id,
                "failure_category": r.category,
                "problem_file": r.problem,
                "seed": r.seed,
                "witness_path": paths.get(r.witness),
                "trace_path": paths.get(r.trace),
                "successors_path": paths.get(r.successors),
                "meta_path": meta_paths[r.id],
                "trace_available": r.trace is not None,
            }
            for r in reps
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return first_failure
