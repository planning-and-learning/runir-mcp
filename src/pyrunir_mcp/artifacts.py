from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
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


def _state_id(state: JsonObject) -> int | None:
    for key in ("id", "state_id", "vertex"):
        value = state.get(key)
        if isinstance(value, int):
            return value
    return None


def _states_by_id(states: list[JsonObject]) -> dict[int, JsonObject]:
    result: dict[int, JsonObject] = {}
    for state in states:
        for key in ("id", "state_id", "vertex"):
            value = state.get(key)
            if isinstance(value, int):
                result.setdefault(value, state)
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


def _ordered_states_for_path(data: JsonObject, state_ids: list[int]) -> list[JsonObject]:
    states = [state for state in data.get("states", []) if isinstance(state, dict)]
    by_id = _states_by_id(states)
    return [dict(by_id[state_id]) for state_id in state_ids if state_id in by_id]


def _path_trace_from_data(data: JsonObject, witness_state_id: int | None) -> JsonObject | None:
    trace = data.get("trace")
    if isinstance(trace, dict):
        return dict(trace)
    transitions = [transition for transition in data.get("transitions", []) if isinstance(transition, dict)]
    if not transitions:
        return None
    state_path = _transition_state_path(transitions)
    if state_path and witness_state_id is not None and witness_state_id in state_path:
        stop = state_path.index(witness_state_id)
        transitions = transitions[:stop]
        state_path = state_path[: stop + 1]
    trace_data = {
        key: data[key]
        for key in ("tool", "task", "problem", "category", "failure_category", "proof_status", "status")
        if key in data
    }
    trace_data.update(
        {
            "states": _ordered_states_for_path(data, state_path) if state_path else [state for state in data.get("states", []) if isinstance(state, dict)],
            "transitions": [dict(transition) for transition in transitions],
            "chosen_actions": [transition.get("action") for transition in transitions if transition.get("action") is not None],
            "trace_available": True,
        }
    )
    return trace_data


def _cycle_payload_from_data(data: JsonObject) -> JsonObject | None:
    cycle = data.get("cycle")
    if not isinstance(cycle, dict):
        return None
    cycle_state_ids = [state_id for state_id in cycle.get("cycle_state_ids", []) if isinstance(state_id, int)]
    cycle_steps = [step for step in cycle.get("cycle_transition_steps", []) if isinstance(step, int)]
    transitions = [transition for transition in data.get("transitions", []) if isinstance(transition, dict)]
    return {
        "cycle": dict(cycle),
        "states": _ordered_states_for_path(data, cycle_state_ids),
        "transitions": [dict(transitions[step]) for step in cycle_steps if 0 <= step < len(transitions)],
    }


def _witness_state_from_data(data: JsonObject) -> JsonObject | None:
    states = [state for state in data.get("states", []) if isinstance(state, dict)]
    if not states:
        return None
    transitions = [transition for transition in data.get("transitions", []) if isinstance(transition, dict)]
    if transitions:
        target = _transition_target(transitions[-1])
        if target is not None:
            by_id = _states_by_id(states)
            if target in by_id:
                return dict(by_id[target])
    return dict(states[0])


def _counterexample_and_trace_payloads(data: JsonObject, category_slug: str) -> tuple[JsonObject, JsonObject | None]:
    if category_slug == "cycle" or isinstance(data.get("cycle"), dict):
        cycle_payload = _cycle_payload_from_data(data)
        if cycle_payload is not None:
            witness_state_id = None
            cycle = cycle_payload.get("cycle")
            if isinstance(cycle, dict):
                cycle_states = cycle.get("cycle_state_ids", [])
                if cycle_states and isinstance(cycle_states[0], int):
                    witness_state_id = cycle_states[0]
            return cycle_payload, _path_trace_from_data(data, witness_state_id)
    state = _witness_state_from_data(data)
    payload = {"state": state} if state is not None else {}
    witness_state_id = _state_id(state) if isinstance(state, dict) else None
    return payload, _path_trace_from_data(data, witness_state_id)


def _write_counterexample_and_trace(
    *,
    output_dir: Path,
    counterexample_id: str,
    category_slug: str,
    data: JsonObject,
) -> tuple[Path, str | None, bool]:
    counterexample_payload, trace_data = _counterexample_and_trace_payloads(data, category_slug)
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
    data = _read_json(source)
    if not isinstance(data, dict):
        data = {"value": data}
    target, trace_path, trace_available = _write_counterexample_and_trace(
        output_dir=output_dir,
        counterexample_id=counterexample_id,
        category_slug=category_slug,
        data=data,
    )
    return CounterexampleItem(
        id=counterexample_id,
        category=category_slug,
        task=task,
        path=relative_to(target, output_dir),
        trace_path=trace_path,
        trace_available=trace_available,
    )


def normalize_trace_dump(
    *,
    tool: str,
    status: str,
    output_dir: Path,
    raw_dump_dir: Path,
    command: CommandResult,
    metadata: JsonObject,
) -> JsonObject:
    output_dir = fresh_output_dir(output_dir)
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
    metadata: JsonObject,
) -> JsonObject:
    output_dir = fresh_output_dir(output_dir)
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

    return write_summary(
        tool=tool,
        status=status,
        output_dir=output_dir,
        command=command,
        metadata=metadata,
        counterexamples=items,
    )


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
