from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.paths import server_output_dir
from pyrunir_mcp.kr.ps.ext.service import TOOL_NAME, prove_module_program as run_prove_module_program


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:

    @mcp.tool(name=TOOL_NAME)
    def prove_module_program(
        domain: str,
        train_dir: str,
        module_program_file: str,
        output_dir: str,
        num_threads: int = 1,
        max_num_states: int = 100_000,
        max_time_seconds: float = 5.0,
        max_arity: int = 0,
        dump_state_mode: str = "summary",
    ) -> dict[str, Any]:
        """Prove an extended Runir module program and write every counterexample separately."""
        return run_prove_module_program(
            ProveModuleProgramOptions(
                domain=domain,
                train_dir=train_dir,
                module_program_file=module_program_file,
                output_dir=server_output_dir(config.output_root, output_dir).as_posix(),
                num_threads=num_threads,
                max_num_states=max_num_states,
                max_time_seconds=max_time_seconds,
                max_arity=max_arity,
                dump_state_mode=dump_state_mode,
            )
        )
