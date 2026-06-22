from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pyrunir_mcp.json_types import JsonObject, JsonValue


class ExecuteResultLike(Protocol):
    failure: object | None

def _read_json(path: Path) -> JsonValue:
    return json.loads(path.read_text(encoding="utf-8"))

def _result_path(value: JsonValue, output_dir: Path) -> str | None:
    if value is None:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path.resolve().as_posix()
    return (output_dir / path).resolve().as_posix()

def _manifest_item(item: JsonValue, output_dir: Path) -> JsonValue:
    if not isinstance(item, dict):
        return item
    copied = dict(item)
    for key in ("trace_path", "counterexample_path"):
        if key in copied:
            copied[key] = _result_path(copied.get(key), output_dir)
    return copied


def _manifest_result(manifest: JsonValue, output_dir: Path) -> JsonValue:
    if not isinstance(manifest, dict):
        return manifest
    data = dict(manifest)
    for key in ("tasks", "distinct_failures"):
        collection = data.get(key)
        if isinstance(collection, list):
            data[key] = [_manifest_item(item, output_dir) for item in collection]
    return data

def _reformat_prompt_summary(
    *,
    tool: str,
    path_key: str,
    artifact_path: str,
    metadata: JsonObject,
) -> JsonObject:
    return {
        "tool": tool,
        "status": "success",
        "successful": True,
        "artifacts": {path_key: artifact_path},
        **metadata,
    }

def reformat_result(*, tool: str, path_key: str, path: Path, **metadata: JsonValue) -> JsonObject:
    artifact_path = path.resolve().as_posix()
    prompt_summary = _reformat_prompt_summary(
        tool=tool,
        path_key=path_key,
        artifact_path=artifact_path,
        metadata=metadata,
    )
    primary = {"successful": True, path_key: artifact_path, "prompt_summary": prompt_summary, **metadata}
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
        "artifacts": {path_key: artifact_path},
        "prompt_summary": prompt_summary,
        "items": [],
        path_key: artifact_path,
        **metadata,
    }

def execute_result(*, tool: str, result: ExecuteResultLike, output_dir: Path) -> JsonObject:
    failure = result.failure
    status = "success" if failure is None else "failure"
    manifest_path = output_dir / "manifest.json"
    summary_md_path = output_dir / "summary.md"
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    result_manifest = _manifest_result(manifest, output_dir)
    tasks = result_manifest.get("tasks", []) if isinstance(result_manifest, dict) else []
    distinct_failures = result_manifest.get("distinct_failures", []) if isinstance(result_manifest, dict) else []

    task_items: list[JsonObject] = []
    failing_task = None
    failing_status = None
    failure_category = None
    for index, task in enumerate(tasks, start=1):
        problem = task.get("problem_file")
        name = Path(str(problem)).name if problem else f"task-{index:03d}"
        trace_path_value = _result_path(task.get("trace_path"), output_dir)
        item = {
            "kind": "task",
            "id": f"task-{index:03d}",
            "name": name,
            "problem_file": problem,
            "status": task.get("status"),
            "failure_category": task.get("failure_category"),
            "seed": task.get("seed"),
            "trace_path": trace_path_value,
        }
        task_items.append(item)
        if failing_task is None and (
            task.get("failure_category") is not None
            or task.get("status") not in (None, "SOLVED", "SUCCESS")
        ):
            failing_task = name
            failing_status = task.get("status")
            failure_category = task.get("failure_category")

    failure_items: list[JsonObject] = []
    for index, item in enumerate(distinct_failures, start=1):
        category = item.get("failure_category") or item.get("status") or "failure"
        failure_id = str(item.get("id") or f"{category}-{index:03d}")
        problem = item.get("problem_file")
        task = item.get("task") or item.get("name") or (Path(str(problem)).name if problem else f"task-{index:03d}")
        trace_path = _result_path(item.get("trace_path"), output_dir)
        counterexample_path = _result_path(item.get("counterexample_path"), output_dir)
        trace_available = bool(trace_path) and trace_path != "<omitted: outside output_dir>"
        failure_items.append({
            "kind": "failure",
            "id": failure_id,
            "category": category,
            "failure_category": item.get("failure_category"),
            "problem_file": problem,
            "task": task,
            "seed": item.get("seed"),
            "path": counterexample_path,
            "trace_path": trace_path,
            "trace_available": bool(item.get("trace_available", trace_available)),
        })
    if failure_category is None and failure_items:
        failure_category = failure_items[0].get("failure_category")
    if failing_task is None and failure_items:
        failing_task = failure_items[0].get("task")

    task_statuses = [(item["name"], item.get("status")) for item in task_items]
    artifacts = {
        "output_dir": output_dir.resolve().as_posix(),
        "manifest_json": manifest_path.resolve().as_posix() if manifest_path.exists() else None,
        "summary_md": summary_md_path.resolve().as_posix() if summary_md_path.exists() else None,
    }
    prompt_summary = {
        "tool": tool,
        "status": status,
        "successful": status == "success",
        "output_dir": output_dir.resolve().as_posix(),
        "manifest_json": artifacts.get("manifest_json"),
        "summary_md": artifacts.get("summary_md"),
        "counts": {
            "tasks": len(task_items),
            "failures": len(failure_items),
        },
        "task_statuses": task_statuses,
        "failure_category": failure_category,
        "failing_task": failing_task,
        "note": "Detailed rollout traces are written under output_dir; start with summary_md/manifest_json.",
    }
    primary = {
        "successful": status == "success",
        "failing_task": failing_task,
        "status": failing_status,
        "failure_category": failure_category,
        "task_statuses": task_statuses,
        "task_count": len(task_items),
        "failure_count": len(failure_items),
        "prompt_summary": prompt_summary,
    }
    summary = {
        "schema_version": 1,
        "tool": tool,
        "status": status,
        "counts": {"tasks": len(task_items), "failures": len(failure_items)},
        "manifest": result_manifest,
        "tasks": task_items,
        "distinct_failures": failure_items,
    }
    return {
        "schema_version": 1,
        "tool": tool,
        "status": status,
        "primary": primary,
        "summary": summary,
        "artifacts": artifacts,
        "prompt_summary": prompt_summary,
        "items": failure_items,
        "tasks": task_items,
        "manifest": result_manifest,
        "manifest_path": artifacts["manifest_json"],
        "summary_md_path": artifacts["summary_md"],
        "output_dir": output_dir.as_posix(),
    }
