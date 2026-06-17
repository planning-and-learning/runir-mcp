from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.ext.reformat.service import ReformatPolicyOptions, reformat_policy

TOOL_NAME = "runir.ps.ext.reformat_module_program"


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    del config

    @mcp.tool(name=TOOL_NAME)
    def reformat_module_program(
        domain: str,
        policy_file: str,
        kind: str = "auto",
    ) -> dict[str, Any]:
        """Parse-check and rewrite an extended Runir module or module program in canonical form."""
        result = reformat_policy(
            ReformatPolicyOptions(
                domain_path=Path(domain).resolve(),
                policy_file=Path(policy_file).resolve(),
                kind=kind,  # type: ignore[arg-type]
            )
        )
        return {"status": "success", "policy_file": result.policy_file.as_posix(), "kind": result.kind}
