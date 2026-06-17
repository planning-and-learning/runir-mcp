from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyrunir_mcp.artifacts import write_native_counterexample_run


def write_example_tool_output(tmp_path: Path, *, tool: str, counterexamples: list[dict[str, Any]]) -> dict[str, Any]:
    return write_native_counterexample_run(
        tool=tool,
        status="failure" if counterexamples else "success",
        output_dir=tmp_path / "run",
        metadata={"example": True},
        counterexamples=counterexamples,
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_common_output(run_dir: Path, result: dict[str, Any], *, expected_count: int) -> dict[str, Any]:
    assert result["output_dir"] == run_dir.as_posix()
    assert result["summary_path"] == "summary.json"
    assert result["summary_md_path"] == "summary.md"
    assert result["artifacts"]["summary_json"] == "summary.json"
    assert result["artifacts"]["summary_md"] == "summary.md"
    assert result["artifacts"]["raw_stdout"] == "raw/stdout.txt"
    assert result["artifacts"]["raw_stderr"] == "raw/stderr.txt"
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
    return summary
