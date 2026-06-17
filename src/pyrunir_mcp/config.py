from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ServerConfig:
    workspace_root: Path
    output_root: Path
    default_timeout_seconds: float = 600.0


def load_config() -> ServerConfig:
    workspace_root = Path(os.environ.get("PYRUNIR_MCP_WORKSPACE", _default_workspace_root())).resolve()
    output_root = Path(
        os.environ.get("PYRUNIR_MCP_OUTPUT_ROOT", workspace_root / "pyrunir-mcp-output")
    ).resolve()
    return ServerConfig(
        workspace_root=workspace_root,
        output_root=output_root,
        default_timeout_seconds=float(os.environ.get("PYRUNIR_MCP_TIMEOUT", "600")),
    )
