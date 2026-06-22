from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest


def _pyproject() -> dict:
    return tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())


def test_console_scripts_are_declared() -> None:
    scripts = _pyproject()["project"]["scripts"]
    assert scripts == {
        "pyrunir-mcp": "pyrunir_mcp.server:main",
        "pyrunir-mcp-invoke": "pyrunir_mcp.invoke:main",
    }


def test_invoke_result_json_writer_does_not_overwrite(tmp_path) -> None:
    from pyrunir_mcp.invoke import _write_result_json

    result_json = tmp_path / "nested" / "result.json"
    _write_result_json(result_json, "first\n")

    with pytest.raises(FileExistsError):
        _write_result_json(result_json, "second\n")

    assert result_json.read_text(encoding="utf-8") == "first\n"


def test_invoke_role_requires_explicit_env(monkeypatch) -> None:
    from pyrunir_mcp.invoke import _ensure_tool_allowed

    monkeypatch.delenv("PYRUNIR_MCP_ROLE", raising=False)

    with pytest.raises(ValueError, match="Runir MCP role is required"):
        _ensure_tool_allowed("missing.role.check")


def test_invoke_role_allows_declared_tool(monkeypatch) -> None:
    from pyrunir_mcp.invoke import _ensure_tool_allowed

    monkeypatch.setenv("PYRUNIR_MCP_ROLE", "kr/ps/base")

    _ensure_tool_allowed("runir.ps.base.prove_sketch_policy")


def test_invoke_role_rejects_disallowed_tool(monkeypatch) -> None:
    from pyrunir_mcp.invoke import _ensure_tool_allowed

    monkeypatch.setenv("PYRUNIR_MCP_ROLE", "kr/ps/base")

    with pytest.raises(PermissionError, match="not allowed"):
        _ensure_tool_allowed("runir.ps.ext.prove_module_program")


def test_invoke_formats_offset_error_with_source_pointer(tmp_path) -> None:
    from pyrunir_mcp.invoke import _format_tool_error

    policy = tmp_path / "module_program.txt"
    policy.write_text("(:program\n  (:memory bad)\n)\n", encoding="utf-8")
    offset = policy.read_text(encoding="utf-8").index("bad")

    result, stderr = _format_tool_error(
        "runir.ps.ext.reformat_module_program",
        {"module_program_file": str(policy)},
        RuntimeError(f"Rule entry section :memory is not valid. at offset {offset}."),
    )

    source = result["primary"]["source"]
    assert result["status"] == "error"
    assert result["primary"]["successful"] is False
    assert source["line"] == 2
    assert source["column"] == 12
    assert source["source_line"] == "  (:memory bad)"
    assert source["pointer"] == "           ^"
    assert f"{policy}:2:12" in stderr
    assert "  (:memory bad)" in stderr
    assert "           ^" in stderr


def test_invoke_main_writes_error_json_without_traceback(monkeypatch, tmp_path, capsys) -> None:
    from pyrunir_mcp import invoke

    policy = tmp_path / "module_program.txt"
    policy.write_text("(:program\n  (:memory bad)\n)\n", encoding="utf-8")
    result_json = tmp_path / "result.json"
    offset = policy.read_text(encoding="utf-8").index("bad")

    def fail(_args):
        raise RuntimeError(f"Rule entry section :memory is not valid. at offset {offset}.")

    monkeypatch.setenv("PYRUNIR_MCP_ROLE", "kr/ps/ext")
    monkeypatch.setitem(invoke.TOOLS, "runir.ps.ext.reformat_module_program", fail)
    monkeypatch.setattr(
        "sys.argv",
        [
            "pyrunir-mcp-invoke",
            "runir.ps.ext.reformat_module_program",
            "--args-json",
            json.dumps({"module_program_file": str(policy)}),
            "--result-json",
            str(result_json),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        invoke.main()

    captured = capsys.readouterr()
    result = json.loads(result_json.read_text(encoding="utf-8"))
    assert excinfo.value.code == 1
    assert result["primary"]["source"]["line"] == 2
    assert "Traceback" not in captured.err
    assert f"{policy}:2:12" in captured.err
