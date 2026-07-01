"""Write a native (prove / termination / classifier) run and build the MCP result envelope.

The service builds the run-global dictionary tables and the per-witness artifacts; this module
writes them (plus a `summary` index) in every format and assembles the envelope that the MCP
layer returns. Execute tools keep their own `manifest.json`-driven path (see `results.py`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pyrunir_mcp.artifacts import fresh_output_dir
from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.output.writer import Artifact, resolve_formats, write_run
from pyrunir_mcp.tables import Fmt, Table


class RunStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class RunCategory(StrEnum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    COUNTEREXAMPLE = "counterexample"


class RunItemCategory(StrEnum):
    SUCCESS = "success"
    CYCLE = "cycle"
    OPEN_STATE = "open_state"
    DEADEND = "deadend"
    DEADEND_TRANSITION = "deadend_transition"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    STRUCTURAL_TERMINATION = "structural_termination"


FailureCategory = RunCategory | RunItemCategory


@dataclass(frozen=True)
class RunItem:
    """One failure, referencing the artifact names written under failures/<id>/."""

    id: str
    category: RunItemCategory
    task: str | None
    witness: str  # artifact name (e.g. "failures/cycle-001/witness")
    trace: str | None = None  # artifact name, when a path trace exists
    successors: str | None = None  # artifact name, when successors were dumped
    plan_trace: str | None = None  # artifact name, when an open-state FF plan was dumped


def _write_item_meta(output_dir: Path, item: RunItem, primary: Fmt) -> str:
    """Write `failures/<id>/meta.json` (the item's index fields + the artifact filenames present) and
    return its absolute path. Always JSON, regardless of the render formats."""
    files = {
        label: f"{label}.{primary}"
        for label, name in (
            ("witness", item.witness),
            ("trace", item.trace),
            ("successors", item.successors),
            ("plan_trace", item.plan_trace),
        )
        if name is not None
    }
    meta = {"id": item.id, "category": item.category.value, "task": item.task, "files": files}
    path = output_dir / "failures" / item.id / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path.resolve().as_posix()


def _summary_table(items: list[RunItem]) -> Table:
    return Table(
        name="summary",
        columns=["id", "category", "task"],
        rows=[[i.id, i.category.value, i.task] for i in items],
    )


def _category_counts(items: list[RunItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        category = item.category.value
        counts[category] = counts.get(category, 0) + 1
    return counts


def _result_item(item: RunItem, paths: dict[str, str], meta_path: str) -> JsonObject:
    return {
        "id": item.id,
        "category": item.category.value,
        "task": item.task,
        "path": paths[item.witness],
        "trace_path": paths[item.trace] if item.trace else None,
        "trace_available": item.trace is not None,
        "successors_path": paths[item.successors] if item.successors else None,
        "plan_trace_path": paths[item.plan_trace] if item.plan_trace else None,
        "meta_path": meta_path,
    }


_STATUS_CATEGORY = {
    "SUCCESS": RunCategory.SUCCESS,
    "OUT_OF_TIME": RunCategory.TIMEOUT,
    "OUT_OF_STATES": RunCategory.RESOURCE_LIMIT,
    "OUT_OF_MEMORY": RunCategory.RESOURCE_LIMIT,
    "FAILURE": RunCategory.COUNTEREXAMPLE,
}


def status_category(status_name: str) -> RunCategory:
    """Map a proof/execution status enum name to the coarse run `category` consumers branch on:
    `success` / `timeout` / `resource_limit` / `counterexample`. A genuine proof failure (a found
    counterexample) is `counterexample`; resource exhaustion is kept distinct so callers can retry
    or accept rather than treat it as a real defect."""
    return _STATUS_CATEGORY.get(status_name.upper(), RunCategory.COUNTEREXAMPLE)


def build_run_envelope(
    *,
    tool: str,
    status: RunStatus,
    output_dir: Path,
    metadata: JsonObject,
    dictionary_tables: dict[str, Table],
    artifacts: dict[str, Artifact],
    items: list[RunItem],
    failure_category: FailureCategory | None = None,
    category: RunCategory | None = None,
    formats: tuple[Fmt, ...] | None = None,
) -> JsonObject:
    output_dir = fresh_output_dir(output_dir)
    # Dictionaries under dicts/; each failure's artifacts under failures/<id>/ (set by the caller).
    paths = write_run(
        output_dir,
        {
            **{f"dicts/{name}": table for name, table in dictionary_tables.items()},
            "summary": _summary_table(items),
            **artifacts,
        },
        formats,
    )
    primary = resolve_formats(formats)[0]
    meta_paths = {item.id: _write_item_meta(output_dir, item, primary) for item in items}

    result_item_objects = [_result_item(item, paths, meta_paths[item.id]) for item in items]
    result_items: list[JsonValue] = list(result_item_objects)
    category_counts: JsonObject = {key: value for key, value in _category_counts(items).items()}
    counts: JsonObject = {"counterexamples": len(items), "categories": len(category_counts)}
    output_path = output_dir.resolve().as_posix()
    prompt_summary: JsonObject = {
        "tool": tool,
        "status": status.value,
        "successful": status is RunStatus.SUCCESS,
        "output_dir": output_path,
        "summary": paths["summary"],
        "counts": counts,
        "category_counts": category_counts,
        "note": "Counterexamples are written under output_dir; start with summary.",
    }
    passthrough: JsonObject = {
        key: metadata[key]
        for key in ("program_status", "nonterminating_modules")
        if key in metadata
    }
    primary_doc: JsonObject = {
        "successful": status is RunStatus.SUCCESS,
        "status": status.value,
        "category": (
            category
            or (RunCategory.SUCCESS if status is RunStatus.SUCCESS else RunCategory.COUNTEREXAMPLE)
        ).value,
        "failure_category": (
            failure_category.value
            if failure_category is not None
            else (result_item_objects[0]["category"] if result_item_objects else None)
        ),
        "counterexample_count": len(result_items),
        "category_counts": category_counts,
        "prompt_summary": prompt_summary,
        **passthrough,
    }
    return {
        "schema_version": 1,
        "tool": tool,
        "status": status.value,
        "primary": primary_doc,
        "summary": {
            "schema_version": 1,
            "tool": tool,
            "status": status.value,
            "metadata": metadata,
            "counts": counts,
            "category_counts": category_counts,
        },
        "artifacts": {"summary": paths["summary"], "output_dir": output_path},
        "prompt_summary": prompt_summary,
        "items": result_items,
        "counts": counts,
        "output_dir": output_path,
    }
