from __future__ import annotations

import json
from pathlib import Path
from pyrunir_mcp.artifacts import write_native_counterexample_run
from pyrunir_mcp.json_types import JsonObject, JsonValue


def write_example_tool_output(tmp_path: Path, *, tool: str, counterexamples: list[JsonObject]) -> JsonObject:
    return write_native_counterexample_run(
        tool=tool,
        status="failure" if counterexamples else "success",
        output_dir=tmp_path / "run",
        metadata={"example": True},
        counterexamples=counterexamples,
    )


def read_json(path: Path) -> JsonValue:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_common_output(run_dir: Path, result: JsonObject, *, expected_count: int) -> JsonObject:
    assert result["output_dir"] == run_dir.as_posix()
    assert result["summary_path"] == (run_dir / "summary.json").as_posix()
    assert result["summary_md_path"] == (run_dir / "summary.md").as_posix()
    assert result["artifacts"]["summary_json"] == (run_dir / "summary.json").as_posix()
    assert result["artifacts"]["summary_md"] == (run_dir / "summary.md").as_posix()
    assert result["artifacts"]["raw_stdout"] == (run_dir / "raw" / "stdout.txt").as_posix()
    assert result["artifacts"]["raw_stderr"] == (run_dir / "raw" / "stderr.txt").as_posix()
    assert (run_dir / "summary.json").is_file()
    assert (run_dir / "summary.md").is_file()
    assert (run_dir / "raw" / "stdout.txt").is_file()
    assert (run_dir / "raw" / "stderr.txt").is_file()

    summary = read_json(run_dir / "summary.json")
    assert summary["schema_version"] == 1
    assert summary["counts"]["counterexamples"] == expected_count
    assert result["counts"] == summary["counts"]
    assert result["primary"]["successful"] is (expected_count == 0)
    assert result["primary"]["counterexample_count"] == expected_count
    assert len(result["items"]) == expected_count
    assert result["summary"] == summary

    prompt_summary = result["prompt_summary"]
    assert result["primary"]["prompt_summary"] == prompt_summary
    assert prompt_summary["output_dir"] == run_dir.as_posix()
    assert prompt_summary["summary_json"] == (run_dir / "summary.json").as_posix()
    assert prompt_summary["summary_md"] == (run_dir / "summary.md").as_posix()
    assert prompt_summary["counts"] == summary["counts"]
    assert "items" not in prompt_summary
    assert "tasks" not in prompt_summary
    return summary
