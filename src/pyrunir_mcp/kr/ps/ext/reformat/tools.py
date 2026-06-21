from __future__ import annotations

from pathlib import Path
from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.ext.reformat.service import ReformatPolicyOptions, reformat_policy
from pyrunir_mcp.paths import server_output_path
from pyrunir_mcp.results import reformat_result

TOOL_NAME = "runir.ps.ext.reformat_module_program"


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    @mcp.tool(name=TOOL_NAME)
    def reformat_module_program(
        domain: str,
        policy_file: str,
        kind: str = "auto",
    ) -> dict:
        """Parse-check and rewrite an extended Runir module or module program in canonical form."""
        result = reformat_policy(
            ReformatPolicyOptions(
                domain_path=Path(domain).resolve(),
                policy_file=server_output_path(config.output_root, policy_file),
                kind=kind,  # type: ignore[arg-type]
            )
        )
        return reformat_result(tool=TOOL_NAME, path_key="policy_file", path=result.policy_file, kind=result.kind)
