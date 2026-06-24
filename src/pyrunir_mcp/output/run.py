"""Write a native (prove / termination / classifier) run and build the MCP result envelope.

The service builds the run-global dictionary tables and the per-witness artifacts; this module
writes them (plus a `summary` index) in every format and assembles the envelope that the MCP
layer returns. Execute tools keep their own `manifest.json`-driven path (see `results.py`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pyrunir_mcp.artifacts import fresh_output_dir
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.output.writer import Artifact, resolve_formats, write_run
from pyrunir_mcp.tables import Fmt, Table


@dataclass(frozen=True)
class RunItem:
    """One failure, referencing the artifact names written under failures/<id>/."""

    id: str
    category: str
    task: str | None
    witness: str  # artifact name (e.g. "failures/cycle-001/witness")
    trace: str | None = None  # artifact name, when a path trace exists
    successors: str | None = None  # artifact name, when successors were dumped


def _write_item_meta(output_dir: Path, item: RunItem, primary: Fmt) -> str:
    """Write `failures/<id>/meta.json` (the item's index fields + the artifact filenames present) and
    return its absolute path. Always JSON, regardless of the render formats."""
    files = {
        label: f"{label}.{primary}"
        for label, name in (("witness", item.witness), ("trace", item.trace), ("successors", item.successors))
        if name is not None
    }
    meta = {"id": item.id, "category": item.category, "task": item.task, "files": files}
    path = output_dir / "failures" / item.id / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path.resolve().as_posix()


def _summary_table(items: list[RunItem]) -> Table:
    return Table(name="summary", columns=["id", "category", "task"], rows=[[i.id, i.category, i.task] for i in items])


def _category_counts(items: list[RunItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category] = counts.get(item.category, 0) + 1
    return counts


def _result_item(item: RunItem, paths: dict[str, str], meta_path: str) -> JsonObject:
    return {
        "id": item.id,
        "category": item.category,
        "task": item.task,
        "path": paths[item.witness],
        "trace_path": paths[item.trace] if item.trace else None,
        "trace_available": item.trace is not None,
        "successors_path": paths[item.successors] if item.successors else None,
        "meta_path": meta_path,
    }


_STATUS_CATEGORY = {
    "SUCCESS": "success",
    "OUT_OF_TIME": "timeout",
    "OUT_OF_STATES": "resource_limit",
    "OUT_OF_MEMORY": "resource_limit",
    "FAILURE": "counterexample",
}


def status_category(status_name: str) -> str:
    """Map a proof/execution status enum name to the coarse run `category` consumers branch on:
    `success` / `timeout` / `resource_limit` / `counterexample`. A genuine proof failure (a found
    counterexample) is `counterexample`; resource exhaustion is kept distinct so callers can retry
    or accept rather than treat it as a real defect."""
    return _STATUS_CATEGORY.get(status_name.upper(), "counterexample")


def build_run_envelope(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    metadata: JsonObject,
    dictionary_tables: dict[str, Table],
    artifacts: dict[str, Artifact],
    items: list[RunItem],
    failure_category: str | None = None,
    category: str | None = None,
    formats: tuple[Fmt, ...] | None = None,
) -> JsonObject:
    output_dir = fresh_output_dir(output_dir)
    # Dictionaries under dicts/; each failure's artifacts under failures/<id>/ (set by the caller).
    paths = write_run(
        output_dir,
        {**{f"dicts/{name}": table for name, table in dictionary_tables.items()}, "summary": _summary_table(items), **artifacts},
        formats,
    )
    primary = resolve_formats(formats)[0]
    meta_paths = {item.id: _write_item_meta(output_dir, item, primary) for item in items}

    result_items = [_result_item(item, paths, meta_paths[item.id]) for item in items]
    category_counts = _category_counts(items)
    counts = {"counterexamples": len(items), "categories": len(category_counts)}
    output_path = output_dir.resolve().as_posix()
    prompt_summary = {
        "tool": tool,
        "status": status,
        "successful": status == "success",
        "output_dir": output_path,
        "summary": paths["summary"],
        "counts": counts,
        "category_counts": category_counts,
        "note": "Counterexamples are written under output_dir; start with summary.",
    }
    passthrough = {key: metadata[key] for key in ("program_status", "nonterminating_modules") if key in metadata}
    primary = {
        "successful": status == "success",
        "status": status,
        "category": category or ("success" if status == "success" else "counterexample"),
        "failure_category": failure_category or (result_items[0]["category"] if result_items else None),
        "counterexample_count": len(result_items),
        "category_counts": category_counts,
        "prompt_summary": prompt_summary,
        **passthrough,
    }
    return {
        "schema_version": 1,
        "tool": tool,
        "status": status,
        "primary": primary,
        "summary": {"schema_version": 1, "tool": tool, "status": status, "metadata": metadata, "counts": counts, "category_counts": category_counts},
        "artifacts": {"summary": paths["summary"], "output_dir": output_path},
        "prompt_summary": prompt_summary,
        "items": result_items,
        "counts": counts,
        "output_dir": output_path,
    }
