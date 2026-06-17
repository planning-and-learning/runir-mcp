from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyrunir_mcp.paths import relative_to


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reformat_result(*, tool: str, path_key: str, path: Path, **metadata: Any) -> dict[str, Any]:
    primary = {"successful": True, path_key: path.as_posix(), **metadata}
    return {
        "schema_version": 1,
        "tool": tool,
        "status": "success",
        "primary": primary,
        "summary": {
            "schema_version": 1,
            "tool": tool,
            "status": "success",
            **primary,
        },
        "artifacts": {path_key: path.as_posix()},
        "items": [],
        path_key: path.as_posix(),
        **metadata,
    }


def execute_result(*, tool: str, result: object, output_dir: Path) -> dict[str, Any]:
    replay_errors = getattr(result, "replay_errors", None) or []
    failure = getattr(result, "failure", None)
    status = "success" if failure is None and not replay_errors else "failure"
    manifest_path = output_dir / "manifest.json"
    summary_md_path = output_dir / "summary.md"
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    tasks = manifest.get("tasks", []) if isinstance(manifest, dict) else []
    distinct_failures = manifest.get("distinct_failures", []) if isinstance(manifest, dict) else []

    task_items: list[dict[str, Any]] = []
    failing_task = None
    failing_status = None
    failure_category = None
    for index, task in enumerate(tasks, start=1):
        problem = task.get("problem")
        name = Path(str(problem)).name if problem else f"task-{index:03d}"
        trace_file = task.get("trace_file")
        item = {
            "kind": "task",
            "id": f"task-{index:03d}",
            "name": name,
            "problem": problem,
            "status": task.get("status"),
            "failure_category": task.get("failure_category"),
            "seed": task.get("seed"),
            "trace_path": trace_file,
        }
        task_items.append(item)
        if failing_task is None and (task.get("failure_category") is not None or task.get("status") not in (None, "SOLVED", "SUCCESS")):
            failing_task = name
            failing_status = task.get("status")
            failure_category = task.get("failure_category")

    failure_items = [
        {
            "kind": "failure",
            "id": f"failure-{index:03d}",
            "fingerprint": item.get("fingerprint"),
            "failure_category": item.get("failure_category"),
            "problem": item.get("problem"),
            "task": Path(str(item.get("problem"))).name if item.get("problem") else None,
            "seed": item.get("seed"),
            "trace_path": item.get("trace_file"),
            "path": item.get("trace_file"),
        }
        for index, item in enumerate(distinct_failures, start=1)
    ]
    if failure_category is None and failure_items:
        failure_category = failure_items[0].get("failure_category")
    if failing_task is None and failure_items:
        failing_task = failure_items[0].get("task")

    primary = {
        "successful": status == "success",
        "failing_task": failing_task,
        "status": failing_status,
        "failure_category": failure_category,
        "task_statuses": [(item["name"], item.get("status")) for item in task_items],
        "replay_errors": replay_errors,
        "task_count": len(task_items),
        "failure_count": len(failure_items),
    }
    artifacts = {
        "output_dir": output_dir.as_posix(),
        "manifest_json": relative_to(manifest_path, output_dir) if manifest_path.exists() else None,
        "summary_md": relative_to(summary_md_path, output_dir) if summary_md_path.exists() else None,
    }
    summary = {
        "schema_version": 1,
        "tool": tool,
        "status": status,
        "counts": {"tasks": len(task_items), "failures": len(failure_items), "replay_errors": len(replay_errors)},
        "manifest": manifest,
        "tasks": task_items,
        "distinct_failures": failure_items,
        "replay_errors": replay_errors,
    }
    return {
        "schema_version": 1,
        "tool": tool,
        "status": status,
        "primary": primary,
        "summary": summary,
        "artifacts": artifacts,
        "items": failure_items,
        "tasks": task_items,
        "manifest": manifest,
        "manifest_path": artifacts["manifest_json"],
        "summary_md_path": artifacts["summary_md"],
        "output_dir": output_dir.as_posix(),
        "replay_errors": replay_errors,
    }
