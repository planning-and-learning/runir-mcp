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
from pyrunir_mcp.kr.ps.proof import StateEvidence, failure_items, witness_artifacts
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.writer import DEFAULT_FORMATS, write_run
from pyrunir_mcp.tables import Table

_SUCCESS = {"SOLVED", "SUCCESS"}

SearchOptions = TypeVar("SearchOptions")


class Task(Protocol):
    @property
    def problem_path(self) -> Path: ...


def is_success_status(status) -> bool:
    return status.name in _SUCCESS


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


def _result_failure(result) -> tuple[str | None, int | list[int] | None]:
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
    counterexample: str | None
    trace: str | None
    successors: str | None


def _relative(name: str | None) -> str:
    return f"{name}.psv" if name else ""


def run_execute(
    *,
    tool: str,
    ext: bool,
    output_dir: Path,
    seeds: list[int],
    tasks: list[Task],
    solve: Callable[[Task, int], object],
    feature_symbols: list[str],
    evidence: StateEvidence,
    dicts: Dictionaries,
    manifest_metadata: JsonObject,
) -> tuple[Task, object] | None:
    """Run rollouts and write the new-format artifacts. Returns the first failing (task, result)."""
    rollouts: list[JsonObject] = []
    task_rows: list[JsonObject] = []
    representatives: dict[tuple[str, str], tuple[int, Task, object, int | list[int] | None]] = {}
    first_failure: tuple[Task, object] | None = None

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

    artifacts: dict[str, object] = {}
    reps: list[_Representative] = []
    for index, ((problem, category), (seed, task, result, witness)) in enumerate(representatives.items(), start=1):
        counterexample_id = f"{category}-{index:03d}"
        names: dict[str, str | None] = {"counterexample": None, "trace": None, "successors": None}
        if witness is not None:
            header = [("tool", tool), ("id", counterexample_id), ("category", category), ("status", result.status.name), ("problem", problem), ("seed", str(seed))]
            counterexample, trace, successors = witness_artifacts(
                result.graph, category, witness, evidence, feature_symbols=feature_symbols, dicts=dicts, ext=ext, header=header
            )
            names["counterexample"] = f"counterexamples/{category}/{counterexample_id}"
            artifacts[names["counterexample"]] = counterexample
            if trace is not None:
                names["trace"] = f"traces/{category}/{counterexample_id}"
                artifacts[names["trace"]] = trace
            if successors is not None:
                names["successors"] = f"successors/{category}/{counterexample_id}"
                artifacts[names["successors"]] = successors
        reps.append(_Representative(counterexample_id, category, result.status.name, seed, problem, names["counterexample"], names["trace"], names["successors"]))

    artifacts["failures"] = Table(
        name="failures",
        columns=["id", "category", "status", "seed", "problem", "source", "trace", "counterexample", "successors"],
        rows=[[r.id, r.category, r.status, r.seed, r.problem, "find_ground_solution", _relative(r.trace), _relative(r.counterexample), _relative(r.successors)] for r in reps],
    )
    artifacts["summary"] = Table(name="summary", columns=["id", "category", "status", "seed", "problem"], rows=[[r.id, r.category, r.status, r.seed, r.problem] for r in reps])

    paths = write_run(output_dir, {**dicts.tables(), **artifacts}, DEFAULT_FORMATS)

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
                "counterexample_path": paths.get(r.counterexample),
                "trace_path": paths.get(r.trace),
                "successors_path": paths.get(r.successors),
                "trace_available": r.trace is not None,
            }
            for r in reps
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return first_failure
