from __future__ import annotations

from pathlib import Path
from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.ext.reformat.service import (
    CreateEmptyPolicyOptions,
    ReformatModuleOptions,
    ReformatModuleProgramOptions,
    create_empty_policy,
    reformat_module,
    reformat_module_program,
)
from pyrunir_mcp.paths import server_output_path
from pyrunir_mcp.results import reformat_result

MODULE_PROGRAM_TOOL_NAME = "runir.ps.ext.reformat_module_program"
MODULE_TOOL_NAME = "runir.ps.ext.reformat_module"
CREATE_EMPTY_TOOL_NAME = "runir.ps.ext.create_empty_module_program"


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    @mcp.tool(name=MODULE_PROGRAM_TOOL_NAME)
    def reformat_extended_module_program(domain_file: str, module_program_file: str) -> dict:
        """Parse-check and rewrite an extended Runir module program in canonical form."""
        result = reformat_module_program(
            ReformatModuleProgramOptions(
                domain_path=Path(domain_file).resolve(),
                module_program_file=server_output_path(config.output_root, module_program_file),
            )
        )
        return reformat_result(
            tool=MODULE_PROGRAM_TOOL_NAME,
            path_key="module_program_file",
            path=result.path,
            kind=result.kind,
        )

    @mcp.tool(name=MODULE_TOOL_NAME)
    def reformat_extended_module(domain_file: str, module_file: str) -> dict:
        """Parse-check and rewrite an extended Runir module in canonical form."""
        result = reformat_module(
            ReformatModuleOptions(
                domain_path=Path(domain_file).resolve(),
                module_file=server_output_path(config.output_root, module_file),
            )
        )
        return reformat_result(
            tool=MODULE_TOOL_NAME,
            path_key="module_file",
            path=result.path,
            kind=result.kind,
        )

    @mcp.tool(name=CREATE_EMPTY_TOOL_NAME)
    def create_empty_module_program(module_program_file: str) -> dict:
        """Write the canonical empty extended Runir module program."""
        result = create_empty_policy(
            CreateEmptyPolicyOptions(module_program_file=server_output_path(config.output_root, module_program_file))
        )
        return reformat_result(
            tool=CREATE_EMPTY_TOOL_NAME,
            path_key="module_program_file",
            path=result.path,
            kind=result.kind,
        )
