from __future__ import annotations

from pathlib import Path
from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.base.reformat.service import CreateEmptyPolicyOptions, ReformatPolicyOptions, create_empty_policy, reformat_policy
from pyrunir_mcp.paths import server_output_path
from pyrunir_mcp.results import reformat_result

TOOL_NAME = "runir.ps.base.reformat_policy"
CREATE_EMPTY_TOOL_NAME = "runir.ps.base.create_empty_policy"


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    @mcp.tool(name=TOOL_NAME)
    def reformat_base_policy(
        domain_file: str,
        sketch_file: str,
    ) -> dict:
        """Parse-check and rewrite a base Runir sketch policy in canonical form."""
        result = reformat_policy(
            ReformatPolicyOptions(
                domain_path=Path(domain_file).resolve(),
                sketch_file=server_output_path(config.output_root, sketch_file),
            )
        )
        return reformat_result(tool=TOOL_NAME, path_key="sketch_file", path=result.sketch_file, kind=result.kind)

    @mcp.tool(name=CREATE_EMPTY_TOOL_NAME)
    def create_empty_base_policy(domain_file: str, sketch_file: str) -> dict:
        """Write the canonical empty base Runir sketch policy."""
        result = create_empty_policy(
            CreateEmptyPolicyOptions(
                domain_path=Path(domain_file).resolve(),
                sketch_file=server_output_path(config.output_root, sketch_file),
            )
        )
        return reformat_result(tool=CREATE_EMPTY_TOOL_NAME, path_key="sketch_file", path=result.sketch_file, kind=result.kind)
