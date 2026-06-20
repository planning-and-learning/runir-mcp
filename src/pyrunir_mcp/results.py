from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any

from pyrunir_mcp.paths import relative_to


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(value: object, default: str = "counterexample") -> str:
    text = str(value or default).strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    return text.strip("_") or default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _result_path(value: object, output_dir: Path) -> str | None:
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(output_dir).as_posix()
    except ValueError:
        return "<omitted: outside output_dir>"


def _manifest_result(manifest: Any, output_dir: Path) -> Any:
    if not isinstance(manifest, dict):
        return manifest
    data = copy.deepcopy(manifest)
    for collection in (data.get("tasks"), data.get("distinct_failures")):
        if not isinstance(collection, list):
            continue
        for item in collection:
            if isinstance(item, dict) and "trace_file" in item:
                item["trace_file"] = _result_path(item.get("trace_file"), output_dir)
    return data


def _reformat_prompt_summary(
    *,
    tool: str,
    path_key: str,
    artifact_path: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "tool": tool,
        "status": "success",
        "successful": True,
        "artifacts": {path_key: artifact_path},
        **metadata,
    }


def reformat_result(*, tool: str, path_key: str, path: Path, **metadata: Any) -> dict[str, Any]:
    artifact_path = path.name
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


def execute_result(*, tool: str, result: object, output_dir: Path) -> dict[str, Any]:
    replay_errors = getattr(result, "replay_errors", None) or []
    failure = getattr(result, "failure", None)
    status = "success" if failure is None and not replay_errors else "failure"
    manifest_path = output_dir / "manifest.json"
    summary_md_path = output_dir / "summary.md"
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    result_manifest = _manifest_result(manifest, output_dir)
    tasks = result_manifest.get("tasks", []) if isinstance(result_manifest, dict) else []
    distinct_failures = result_manifest.get("distinct_failures", []) if isinstance(result_manifest, dict) else []

    task_items: list[dict[str, Any]] = []
    failing_task = None
    failing_status = None
    failure_category = None
    for index, task in enumerate(tasks, start=1):
        problem = task.get("problem")
        name = Path(str(problem)).name if problem else f"task-{index:03d}"
        trace_file = _result_path(task.get("trace_file"), output_dir)
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
        if failing_task is None and (
            task.get("failure_category") is not None
            or task.get("status") not in (None, "SOLVED", "SUCCESS")
        ):
            failing_task = name
            failing_status = task.get("status")
            failure_category = task.get("failure_category")

    failure_items: list[dict[str, Any]] = []
    failing_tasks = [
        item
        for item in task_items
        if item.get("failure_category") is not None
        or item.get("status") not in (None, "SOLVED", "SUCCESS")
    ]
    for index, item in enumerate(failing_tasks, start=1):
        category = _slug(item.get("failure_category") or item.get("status"), "failure")
        failure_id = f"{category}-{index:03d}"
        problem = item.get("problem")
        task = item.get("name")
        source_trace_path = item.get("trace_path")
        trace_path = None
        trace_available = False
        if source_trace_path and source_trace_path != "<omitted: outside output_dir>":
            source = output_dir / str(source_trace_path)
            if source.is_file():
                trace_target = output_dir / "traces" / category / f"{failure_id}.json"
                trace_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, trace_target)
                trace_path = trace_target.relative_to(output_dir).as_posix()
                trace_available = True
        counterexample_path = output_dir / "counterexamples" / category / f"{failure_id}.json"
        counterexample = {
            "schema_version": 1,
            "id": failure_id,
            "category": category,
            "kind": "failure",
            "failure_category": item.get("failure_category"),
            "problem": problem,
            "task": task,
            "seed": item.get("seed"),
            "source_trace_path": source_trace_path,
            "trace_available": trace_available,
        }
        if trace_path is not None:
            counterexample["trace_path"] = trace_path
        _write_json(counterexample_path, counterexample)
        failure_items.append({
            "kind": "failure",
            "id": failure_id,
            "category": category,
            "failure_category": item.get("failure_category"),
            "problem": problem,
            "task": task,
            "seed": item.get("seed"),
            "path": counterexample_path.relative_to(output_dir).as_posix(),
            "trace_path": trace_path,
            "trace_available": trace_available,
            "source_trace_path": source_trace_path,
        })
    if failure_category is None and failure_items:
        failure_category = failure_items[0].get("failure_category")
    if failing_task is None and failure_items:
        failing_task = failure_items[0].get("task")

    task_statuses = [(item["name"], item.get("status")) for item in task_items]
    artifacts = {
        "output_dir": output_dir.as_posix(),
        "manifest_json": relative_to(manifest_path, output_dir) if manifest_path.exists() else None,
        "summary_md": relative_to(summary_md_path, output_dir) if summary_md_path.exists() else None,
    }
    prompt_summary = {
        "tool": tool,
        "status": status,
        "successful": status == "success",
        "output_dir": output_dir.as_posix(),
        "manifest_json": artifacts.get("manifest_json"),
        "summary_md": artifacts.get("summary_md"),
        "counts": {
            "tasks": len(task_items),
            "failures": len(failure_items),
            "replay_errors": len(replay_errors),
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
        "replay_errors": replay_errors,
        "task_count": len(task_items),
        "failure_count": len(failure_items),
        "prompt_summary": prompt_summary,
    }
    summary = {
        "schema_version": 1,
        "tool": tool,
        "status": status,
        "counts": {"tasks": len(task_items), "failures": len(failure_items), "replay_errors": len(replay_errors)},
        "manifest": result_manifest,
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
        "prompt_summary": prompt_summary,
        "items": failure_items,
        "tasks": task_items,
        "manifest": result_manifest,
        "manifest_path": artifacts["manifest_json"],
        "summary_md_path": artifacts["summary_md"],
        "output_dir": output_dir.as_posix(),
        "replay_errors": replay_errors,
    }
