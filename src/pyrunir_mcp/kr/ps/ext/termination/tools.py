from __future__ import annotations

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.ext.termination.schemas import ProveTerminationOptions
from pyrunir_mcp.kr.ps.ext.termination.service import TOOL_NAME
from pyrunir_mcp.paths import server_output_dir
from pyrunir_mcp.kr.ps.ext.termination.service import prove_termination as run_prove_termination


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:

    @mcp.tool(name=TOOL_NAME)
    def prove_termination(
        domain: str,
        module_program_file: str,
        output_dir: str,
    ) -> dict:
        """Prove structural termination for an extended Runir module program."""
        return run_prove_termination(
            ProveTerminationOptions(
                domain=domain,
                module_program_file=module_program_file,
                output_dir=server_output_dir(config.output_root, output_dir).as_posix(),
            )
        )
