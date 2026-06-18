from __future__ import annotations

import asyncio

import pytest

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.roles import (
    KR_PS_BASE_TOOLS,
    KR_PS_EXT_TOOLS,
    KR_UNS_TOOLS,
    ALL_TOOLS,
    Role,
    load_role,
)
from pyrunir_mcp.server import create_server


def _config(tmp_path):
    return ServerConfig(workspace_root=tmp_path, output_root=tmp_path / "out")


def _tool_names(server) -> set[str]:
    return {tool.name for tool in asyncio.run(server.list_tools())}


@pytest.mark.parametrize(
    ("role_name", "allowed"),
    [
        ("kr/ps/base", KR_PS_BASE_TOOLS),
        ("kr/ps/ext", KR_PS_EXT_TOOLS),
        ("kr/uns", KR_UNS_TOOLS),
    ],
)
def test_create_server_registers_only_role_tools(tmp_path, role_name, allowed):
    server = create_server(
        config=_config(tmp_path),
        role=Role(name=role_name, allowed_tools=allowed),
    )

    assert _tool_names(server) == set(allowed) | {"pyrunir_mcp.server_info"}


def test_all_role_exposes_every_declared_tool(tmp_path):
    server = create_server(
        config=_config(tmp_path),
        role=Role(name="all", allowed_tools=ALL_TOOLS),
    )

    assert _tool_names(server) == set(ALL_TOOLS) | {"pyrunir_mcp.server_info"}


def test_load_role_accepts_aliases(monkeypatch):
    monkeypatch.setenv("PYRUNIR_MCP_ROLE", "kr.ps.base")

    role = load_role()

    assert role.name == "kr.ps.base"
    assert role.allowed_tools == KR_PS_BASE_TOOLS


def test_load_role_requires_explicit_env(monkeypatch):
    monkeypatch.delenv("PYRUNIR_MCP_ROLE", raising=False)

    with pytest.raises(ValueError, match="Runir MCP role is required"):
        load_role()


def test_load_role_rejects_unknown(monkeypatch):
    monkeypatch.setenv("PYRUNIR_MCP_ROLE", "unknown")

    with pytest.raises(ValueError, match="Unknown PYRUNIR_MCP_ROLE"):
        load_role()


def test_invoke_rejects_tool_outside_role(monkeypatch):
    from pyrunir_mcp.invoke import _ensure_tool_allowed

    monkeypatch.setenv("PYRUNIR_MCP_ROLE", "kr/ps/base")

    with pytest.raises(PermissionError, match="not allowed"):
        _ensure_tool_allowed("runir.uns.prove_classifier")


def test_invoke_allows_tool_inside_role(monkeypatch):
    from pyrunir_mcp.invoke import _ensure_tool_allowed

    monkeypatch.setenv("PYRUNIR_MCP_ROLE", "kr/ps/base")

    _ensure_tool_allowed("runir.ps.base.prove_sketch_policy")

