from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.base.reformat.service import ReformatPolicyOptions, reformat_policy
from pyrunir_mcp.paths import server_output_path
from pyrunir_mcp.results import reformat_result

TOOL_NAME = "runir.ps.base.reformat_policy"


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    @mcp.tool(name=TOOL_NAME)
    def reformat_base_policy(
        domain: str,
        policy_file: str,
        kind: str = "auto",
        create_empty: bool = False,
    ) -> dict[str, Any]:
        """Parse-check and rewrite a base Runir sketch policy in canonical form."""
        result = reformat_policy(
            ReformatPolicyOptions(
                domain_path=Path(domain).resolve(),
                policy_file=server_output_path(config.output_root, policy_file),
                kind=kind,  # type: ignore[arg-type]
                create_empty=create_empty,
            )
        )
        return reformat_result(tool=TOOL_NAME, path_key="policy_file", path=result.policy_file, kind=result.kind)
