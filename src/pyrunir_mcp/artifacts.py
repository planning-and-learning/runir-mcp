from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pyrunir_mcp.counterexample_payloads import counterexample_and_trace_payloads
from pyrunir_mcp.json_types import JsonObject, JsonValue

from pyrunir_mcp.paths import relative_to

@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str

@dataclass(frozen=True)
class CounterexampleItem:
    id: str
    category: str
    task: str | None
    path: str
    trace_path: str | None = None
    trace_available: bool = False

def _slug(value, default: str = "counterexample") -> str:
    text = str(value or default).strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    return text.strip("_") or default



RESERVATION_MARKER = ".pyrunir-mcp-output"

def _has_existing_run_output(output_dir: Path) -> bool:
    return any(
        (output_dir / name).exists()
        for name in (
            RESERVATION_MARKER,
            "summary.json",
            "summary.md",
            "counterexamples",
            "traces",
            "raw",
            "manifest.json",
            "failures",
        )
    )

def _reserve_output_dir(output_dir: Path) -> bool:
    output_dir.mkdir(parents=True, exist_ok=True)
    if _has_existing_run_output(output_dir):
        return False
    try:
        with (output_dir / RESERVATION_MARKER).open("x", encoding="utf-8") as fh:
            fh.write("reserved\n")
    except FileExistsError:
        return False
    return True

def fresh_output_dir(output_dir: Path) -> Path:
    """Return an output dir that will not overwrite a previous MCP run.

    App orchestration often pre-creates an empty trial directory before invoking a
    tool; that remains the primary output dir. If the same directory is reused and
    already contains a prior MCP summary/raw/counterexample tree, allocate a
    numbered child under it so every call remains inspectable.
    """
    if _reserve_output_dir(output_dir):
        return output_dir
    for index in range(2, 10000):
        candidate = output_dir / f"run-{index:03d}"
        if _reserve_output_dir(candidate):
            return candidate
    raise RuntimeError(f"could not allocate fresh MCP output directory under {output_dir}")

def _read_json(path: Path) -> JsonValue:
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, data: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")

def _write_counterexample_and_trace(
    *,
    output_dir: Path,
    counterexample_id: str,
    category_slug: str,
    data: JsonObject,
) -> tuple[Path, str | None, bool]:
    counterexample_payload, trace_data = counterexample_and_trace_payloads(
        data,
        category_slug,
        trace_metadata_keys=("tool", "task", "problem", "category", "failure_category", "proof_status", "status"),
    )
    trace_path: str | None = None
    trace_available = False
    if trace_data is not None:
        trace_target = output_dir / "traces" / category_slug / f"{counterexample_id}.json"
        trace_data.setdefault("schema_version", 1)
        trace_data.setdefault("id", counterexample_id)
        trace_data.setdefault("category", category_slug)
        _write_json(trace_target, trace_data)
        trace_path = relative_to(trace_target, output_dir)
        trace_available = True

    target = output_dir / "counterexamples" / category_slug / f"{counterexample_id}.json"
    stored = {
        key: value
        for key, value in data.items()
        if key not in {"states", "transitions", "trace"}
    }
    stored.update(counterexample_payload)
    stored.setdefault("schema_version", 1)
    stored.setdefault("id", counterexample_id)
    stored.setdefault("category", category_slug)
    stored["trace_available"] = trace_available
    if trace_path is not None:
        stored["trace_path"] = trace_path
    _write_json(target, stored)
    return target, trace_path, trace_available

def _prompt_summary(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    artifacts: JsonObject,
    counts: JsonObject,
    category_counts: dict[str, int],
    task_statuses: list[tuple[JsonValue, JsonValue]],
) -> JsonObject:
    summary = {
        "tool": tool,
        "status": status,
        "successful": status == "success",
        "output_dir": output_dir.as_posix(),
        "summary_json": artifacts.get("summary_json"),
        "summary_md": artifacts.get("summary_md"),
        "counts": counts,
        "category_counts": category_counts,
        "task_statuses": task_statuses,
        "note": "Detailed counterexamples are written under output_dir; start with summary_md/summary_json.",
    }
    if tool == "runir.uns.prove_classifier":
        summary["classifier_semantics"] = {
            "true": "predicted unsolvable",
            "false": "predicted solvable",
            "false_positive": "true on a solvable state",
            "false_negative": "false on an unsolvable state",
        }
    return summary

def write_summary(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    command: CommandResult,
    metadata: JsonObject,
    counterexamples: list[CounterexampleItem],
) -> JsonObject:
    by_category: dict[str, JsonObject] = {}
    grouped: dict[str, list[CounterexampleItem]] = defaultdict(list)
    for item in counterexamples:
        grouped[item.category].append(item)
    for category, values in sorted(grouped.items()):
        by_category[category] = {
            "count": len(values),
            "items": [item.__dict__ for item in values],
        }

    tasks: dict[str, list[CounterexampleItem]] = defaultdict(list)
    for item in counterexamples:
        if item.task is not None:
            tasks[item.task].append(item)

    summary = {
        "schema_version": 1,
        "tool": tool,
        "status": status,
        "metadata": metadata,
        "counts": {
            "counterexamples": len(counterexamples),
            "categories": len(by_category),
            "tasks_with_counterexamples": len(tasks),
        },
        "by_category": by_category,
        "tasks": [
            {
                "name": task,
                "counterexamples": [item.__dict__ for item in values],
            }
            for task, values in sorted(tasks.items())
        ],
        "raw": {
            "stdout_path": "raw/stdout.txt",
            "stderr_path": "raw/stderr.txt",
            "dump_dir": "raw",
        },
        "command": {
            "args": command.args,
            "cwd": command.cwd.as_posix(),
            "returncode": command.returncode,
        },
    }

    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with (raw_dir / "stdout.txt").open("x", encoding="utf-8") as fh:
        fh.write(command.stdout)
    with (raw_dir / "stderr.txt").open("x", encoding="utf-8") as fh:
        fh.write(command.stderr)
    _write_json(output_dir / "summary.json", summary)
    write_summary_markdown(output_dir / "summary.md", summary)

    flat_items = [item.__dict__ for item in counterexamples]
    failure_category = flat_items[0]["category"] if flat_items else None
    per_task = [task for task in metadata.get("per_task", []) if isinstance(task, dict)]
    task_statuses = [
        (task.get("task") or task.get("name"), task.get("status"))
        for task in per_task
    ]
    if not task_statuses:
        task_statuses = [(task["name"], "counterexample") for task in summary["tasks"]]
    category_counts = {category: data["count"] for category, data in by_category.items()}
    artifacts = {
        "summary_json": relative_to(output_dir / "summary.json", output_dir),
        "summary_md": relative_to(output_dir / "summary.md", output_dir),
        "raw_stdout": "raw/stdout.txt",
        "raw_stderr": "raw/stderr.txt",
        "output_dir": output_dir.as_posix(),
    }
    prompt_summary = _prompt_summary(
        tool=tool,
        status=status,
        output_dir=output_dir,
        artifacts=artifacts,
        counts=summary["counts"],
        category_counts=category_counts,
        task_statuses=task_statuses,
    )
    primary = {
        "successful": status == "success",
        "failure_category": failure_category,
        "category": (
            "success"
            if status == "success"
            else (
                "resource_limit"
                if failure_category == "resource_limit"
                else "counterexample"
                if failure_category
                else "unknown"
            )
        ),
        "task_statuses": task_statuses,
        "per_task": per_task,
        "counterexample_count": len(flat_items),
        "category_counts": category_counts,
        "prompt_summary": prompt_summary,
        **{
            key: metadata[key]
            for key in ("program_status", "nonterminating_modules")
            if key in metadata
        },
    }
    return {
        "schema_version": summary["schema_version"],
        "tool": tool,
        "status": status,
        "primary": primary,
        "summary": summary,
        "artifacts": artifacts,
        "prompt_summary": prompt_summary,
        "items": flat_items,
        "tasks": summary["tasks"],
        "summary_path": artifacts["summary_json"],
        "summary_md_path": artifacts["summary_md"],
        "output_dir": output_dir.as_posix(),
        "counts": summary["counts"],
        "by_category": by_category,
    }

def write_summary_markdown(path: Path, summary: JsonObject) -> None:
    lines = [
        f"# {summary['tool']}",
        "",
        f"Status: `{summary['status']}`",
        "",
        "## Counts",
        "",
        f"- Counterexamples: {summary['counts']['counterexamples']}",
        f"- Categories: {summary['counts']['categories']}",
        f"- Tasks with counterexamples: {summary['counts']['tasks_with_counterexamples']}",
        "",
        "## Counterexamples",
        "",
    ]
    if not summary["by_category"]:
        lines.append("No counterexamples.")
    for category, data in summary["by_category"].items():
        lines.append(f"### {category} ({data['count']})")
        lines.append("")
        for item in data["items"]:
            task = f" task `{item['task']}`" if item.get("task") else ""
            line = f"- `{item['id']}`{task}: `{item['path']}`"
            if item.get("trace_available") and item.get("trace_path"):
                line += f"; trace `{item['trace_path']}`"
            lines.append(line)
        lines.append("")
    with path.open("x", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")

def write_native_counterexample_run(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    metadata: JsonObject,
    counterexamples: list[JsonObject],
) -> JsonObject:
    output_dir = fresh_output_dir(output_dir)
    items: list[CounterexampleItem] = []
    for index, counterexample in enumerate(counterexamples, start=1):
        category = _slug(counterexample.get("category"), "counterexample")
        counterexample_id = f"{category}-{index:03d}"
        data = dict(counterexample)
        target, trace_path, trace_available = _write_counterexample_and_trace(
            output_dir=output_dir,
            counterexample_id=counterexample_id,
            category_slug=category,
            data=data,
        )
        items.append(
            CounterexampleItem(
                id=counterexample_id,
                category=category,
                task=data.get("task"),
                path=relative_to(target, output_dir),
                trace_path=trace_path,
                trace_available=trace_available,
            )
        )

    command = CommandResult(args=[], cwd=Path.cwd(), returncode=0 if status == "success" else 1, stdout="", stderr="")
    return write_summary(
        tool=tool,
        status=status,
        output_dir=output_dir,
        command=command,
        metadata=metadata,
        counterexamples=items,
    )
