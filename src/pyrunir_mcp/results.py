from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from pyrunir_mcp.json_types import JsonObject, JsonValue

from pyrunir_mcp.paths import relative_to


def _read_json(path: Path) -> JsonValue:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(value, default: str = "counterexample") -> str:
    text = str(value or default).strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    return text.strip("_") or default


def _write_json(path: Path, data: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _result_path(value, output_dir: Path) -> str | None:
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(output_dir).as_posix()
    except ValueError:
        return "<omitted: outside output_dir>"


def _manifest_result(manifest: JsonValue, output_dir: Path) -> JsonValue:
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


def _state_id(state: JsonObject) -> int | None:
    value = state.get("id", state.get("state_id"))
    if isinstance(value, int):
        return value
    return None


def _states_by_id(states: list[JsonObject]) -> dict[int, JsonObject]:
    result: dict[int, JsonObject] = {}
    for state in states:
        state_id = _state_id(state)
        if state_id is not None:
            result.setdefault(state_id, state)
    return result


def _transition_source(transition: JsonObject) -> int | None:
    value = transition.get("source_state", transition.get("source"))
    return value if isinstance(value, int) else None


def _transition_target(transition: JsonObject) -> int | None:
    value = transition.get("target_state", transition.get("target"))
    return value if isinstance(value, int) else None


def _transition_state_path(transitions: list[JsonObject]) -> list[int]:
    if not transitions:
        return []
    first = _transition_source(transitions[0])
    if first is None:
        return []
    state_ids = [first]
    for transition in transitions:
        target = _transition_target(transition)
        if target is None:
            return state_ids
        state_ids.append(target)
    return state_ids


def _ordered_states_for_path(source: JsonObject, state_ids: list[int]) -> list[JsonObject]:
    by_id = _states_by_id([state for state in source.get("states", []) if isinstance(state, dict)])
    return [copy.deepcopy(by_id[state_id]) for state_id in state_ids if state_id in by_id]


def _path_trace_from_source(source: JsonObject, witness_state_id: int | None) -> JsonObject | None:
    transitions = [t for t in source.get("transitions", []) if isinstance(t, dict)]
    if not transitions:
        return None
    state_path = _transition_state_path(transitions)
    if not state_path:
        return None
    if witness_state_id is not None and witness_state_id in state_path:
        stop = state_path.index(witness_state_id)
        transitions = transitions[:stop]
        state_path = state_path[: stop + 1]
    trace = {
        key: copy.deepcopy(source[key])
        for key in (
            "artifact_version",
            "tool",
            "domain_file",
            "problem_file",
            "sketch_file",
            "sketch_sha256",
            "module_program_file",
            "module_program_sha256",
            "options",
            "status",
            "failure_category",
            "task_index",
            "features",
        )
        if key in source
    }
    trace.update(
        {
            "states": _ordered_states_for_path(source, state_path),
            "transitions": copy.deepcopy(transitions),
            "chosen_actions": [transition.get("action") for transition in transitions if transition.get("action") is not None],
            "trace_available": True,
        }
    )
    return trace


def _cycle_counterexample_from_source(source: JsonObject) -> JsonObject | None:
    cycle = source.get("cycle")
    if not isinstance(cycle, dict):
        return None
    cycle_state_ids = [state_id for state_id in cycle.get("cycle_state_ids", []) if isinstance(state_id, int)]
    cycle_steps = [step for step in cycle.get("cycle_transition_steps", []) if isinstance(step, int)]
    transitions = [t for t in source.get("transitions", []) if isinstance(t, dict)]
    cycle_transitions = [copy.deepcopy(transitions[step]) for step in cycle_steps if 0 <= step < len(transitions)]
    data = {
        "cycle": copy.deepcopy(cycle),
        "states": _ordered_states_for_path(source, cycle_state_ids),
        "transitions": cycle_transitions,
        "chosen_actions": [transition.get("action") for transition in cycle_transitions if transition.get("action") is not None],
    }
    return data


def _witness_state_from_source(source: JsonObject) -> JsonObject | None:
    states = [state for state in source.get("states", []) if isinstance(state, dict)]
    if not states:
        return None
    transitions = [t for t in source.get("transitions", []) if isinstance(t, dict)]
    if transitions:
        target = _transition_target(transitions[-1])
        if target is not None:
            by_id = _states_by_id(states)
            if target in by_id:
                return copy.deepcopy(by_id[target])
    return copy.deepcopy(states[0])


def _counterexample_payload_from_source(source: JsonObject, category: str) -> tuple[JsonObject, JsonObject | None]:
    if category == "cycle" or isinstance(source.get("cycle"), dict):
        cycle_payload = _cycle_counterexample_from_source(source)
        if cycle_payload is not None:
            witness_state_id = None
            cycle = cycle_payload.get("cycle")
            if isinstance(cycle, dict):
                cycle_states = cycle.get("cycle_state_ids", [])
                if cycle_states and isinstance(cycle_states[0], int):
                    witness_state_id = cycle_states[0]
            return cycle_payload, _path_trace_from_source(source, witness_state_id)
    state = _witness_state_from_source(source)
    payload: JsonObject = {"state": state} if state is not None else {}
    witness_state_id = _state_id(state) if isinstance(state, dict) else None
    return payload, _path_trace_from_source(source, witness_state_id)


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


def execute_result(*, tool: str, result, output_dir: Path) -> JsonObject:
    replay_errors = getattr(result, "replay_errors", None) or []
    failure = getattr(result, "failure", None)
    status = "success" if failure is None and not replay_errors else "failure"
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
        trace_file = _result_path(task.get("trace_file"), output_dir)
        item = {
            "kind": "task",
            "id": f"task-{index:03d}",
            "name": name,
            "problem_file": problem,
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

    failure_items: list[JsonObject] = []
    failing_tasks = [
        item
        for item in task_items
        if item.get("failure_category") is not None
        or item.get("status") not in (None, "SOLVED", "SUCCESS")
    ]
    failure_sources = distinct_failures if distinct_failures else failing_tasks
    for index, item in enumerate(failure_sources, start=1):
        category = _slug(item.get("failure_category") or item.get("status"), "failure")
        failure_id = f"{category}-{index:03d}"
        problem = item.get("problem_file")
        task = item.get("task") or item.get("name") or (Path(str(problem)).name if problem else f"task-{index:03d}")
        source_trace_path = _result_path(item.get("trace_file") or item.get("trace_path"), output_dir)
        trace_path = None
        trace_available = False
        counterexample_payload: JsonObject = {}
        if source_trace_path and source_trace_path != "<omitted: outside output_dir>":
            source = output_dir / str(source_trace_path)
            if source.is_file():
                source_data = _read_json(source)
                if isinstance(source_data, dict):
                    counterexample_payload, trace_data = _counterexample_payload_from_source(source_data, category)
                    if trace_data is not None:
                        trace_target = output_dir / "traces" / category / f"{failure_id}.json"
                        trace_data.setdefault("schema_version", 1)
                        trace_data.setdefault("id", failure_id)
                        trace_data.setdefault("category", category)
                        _write_json(trace_target, trace_data)
                        trace_path = trace_target.relative_to(output_dir).as_posix()
                        trace_available = True
        counterexample_path = output_dir / "counterexamples" / category / f"{failure_id}.json"
        counterexample = {
            "schema_version": 1,
            "id": failure_id,
            "category": category,
            "kind": "failure",
            "failure_category": item.get("failure_category"),
            "problem_file": problem,
            "task": task,
            "seed": item.get("seed"),
            "source_trace_path": source_trace_path,
            "trace_available": trace_available,
            **counterexample_payload,
        }
        if trace_path is not None:
            counterexample["trace_path"] = trace_path
        _write_json(counterexample_path, counterexample)
        failure_items.append({
            "kind": "failure",
            "id": failure_id,
            "category": category,
            "failure_category": item.get("failure_category"),
            "problem_file": problem,
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
