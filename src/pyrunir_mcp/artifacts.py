from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def _slug(value: object, default: str = "counterexample") -> str:
    text = str(value or default).strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "_", text)
    return text.strip("_") or default


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _copy_counterexample(
    *,
    source: Path,
    output_dir: Path,
    index: int,
    category: str,
    task: str | None,
) -> CounterexampleItem:
    category_slug = _slug(category)
    counterexample_id = f"{category_slug}-{index:03d}"
    target = output_dir / "counterexamples" / category_slug / f"{counterexample_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _read_json(source)
    if isinstance(data, dict):
        data.setdefault("schema_version", 1)
        data.setdefault("id", counterexample_id)
        data.setdefault("category", category_slug)
    _write_json(target, data)
    return CounterexampleItem(
        id=counterexample_id,
        category=category_slug,
        task=task,
        path=relative_to(target, output_dir),
    )


def normalize_trace_dump(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    raw_dump_dir: Path,
    command: CommandResult,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_target = output_dir / "raw"
    if raw_target.exists():
        shutil.rmtree(raw_target)
    if raw_dump_dir.exists():
        shutil.copytree(raw_dump_dir, raw_target)
    else:
        raw_target.mkdir(parents=True, exist_ok=True)

    items: list[CounterexampleItem] = []
    for index, trace_path in enumerate(sorted(raw_target.glob("task-*.json")), start=1):
        data = _read_json(trace_path)
        category = str(data.get("failure_category") or data.get("category") or "counterexample")
        task = data.get("problem") or data.get("task")
        task_name = Path(str(task)).name if task is not None else None
        items.append(
            _copy_counterexample(
                source=trace_path,
                output_dir=output_dir,
                index=index,
                category=category,
                task=task_name,
            )
        )

    return write_summary(
        tool=tool,
        status=status,
        output_dir=output_dir,
        command=command,
        metadata=metadata,
        counterexamples=items,
    )


def normalize_unsolvability_dump(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    raw_dump_dir: Path,
    command: CommandResult,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_target = output_dir / "raw"
    if raw_target.exists():
        shutil.rmtree(raw_target)
    if raw_dump_dir.exists():
        shutil.copytree(raw_dump_dir, raw_target)
    else:
        raw_target.mkdir(parents=True, exist_ok=True)

    source = raw_target / "counterexamples.json"
    counterexamples = _read_json(source) if source.exists() else []
    items: list[CounterexampleItem] = []
    for index, counterexample in enumerate(counterexamples, start=1):
        category = _slug(counterexample.get("category"), "counterexample")
        counterexample_id = f"{category}-{index:03d}"
        target = output_dir / "counterexamples" / category / f"{counterexample_id}.json"
        data = dict(counterexample)
        data.setdefault("schema_version", 1)
        data.setdefault("id", counterexample_id)
        _write_json(target, data)
        items.append(
            CounterexampleItem(
                id=counterexample_id,
                category=category,
                task=data.get("task"),
                path=relative_to(target, output_dir),
            )
        )

    return write_summary(
        tool=tool,
        status=status,
        output_dir=output_dir,
        command=command,
        metadata=metadata,
        counterexamples=items,
    )


def write_summary(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    command: CommandResult,
    metadata: dict[str, Any],
    counterexamples: list[CounterexampleItem],
) -> dict[str, Any]:
    by_category: dict[str, dict[str, Any]] = {}
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
    (raw_dir / "stdout.txt").write_text(command.stdout, encoding="utf-8")
    (raw_dir / "stderr.txt").write_text(command.stderr, encoding="utf-8")
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
    primary = {
        "successful": status == "success",
        "failure_category": failure_category,
        "category": "success" if status == "success" else ("resource_limit" if failure_category == "resource_limit" else "counterexample" if failure_category else "unknown"),
        "task_statuses": task_statuses,
        "per_task": per_task,
        "counterexample_count": len(flat_items),
        "category_counts": category_counts,
        **{
            key: metadata[key]
            for key in ("program_status", "nonterminating_modules")
            if key in metadata
        },
    }
    artifacts = {
        "summary_json": relative_to(output_dir / "summary.json", output_dir),
        "summary_md": relative_to(output_dir / "summary.md", output_dir),
        "raw_stdout": "raw/stdout.txt",
        "raw_stderr": "raw/stderr.txt",
        "output_dir": output_dir.as_posix(),
    }
    return {
        "schema_version": summary["schema_version"],
        "tool": tool,
        "status": status,
        "primary": primary,
        "summary": summary,
        "artifacts": artifacts,
        "items": flat_items,
        "tasks": summary["tasks"],
        "summary_path": artifacts["summary_json"],
        "summary_md_path": artifacts["summary_md"],
        "output_dir": output_dir.as_posix(),
        "counts": summary["counts"],
        "by_category": by_category,
    }


def write_summary_markdown(path: Path, summary: dict[str, Any]) -> None:
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
            lines.append(f"- `{item['id']}`{task}: `{item['path']}`")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_native_counterexample_run(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    metadata: dict[str, Any],
    counterexamples: list[dict[str, Any]],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    items: list[CounterexampleItem] = []
    for index, counterexample in enumerate(counterexamples, start=1):
        category = _slug(counterexample.get("category"), "counterexample")
        counterexample_id = f"{category}-{index:03d}"
        target = output_dir / "counterexamples" / category / f"{counterexample_id}.json"
        data = dict(counterexample)
        data.setdefault("schema_version", 1)
        data.setdefault("id", counterexample_id)
        data.setdefault("category", category)
        _write_json(target, data)
        items.append(
            CounterexampleItem(
                id=counterexample_id,
                category=category,
                task=data.get("task"),
                path=relative_to(target, output_dir),
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
