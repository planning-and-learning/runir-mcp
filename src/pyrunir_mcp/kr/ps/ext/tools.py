from __future__ import annotations

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.paths import server_output_dir
from pyrunir_mcp.kr.ps.ext.service import TOOL_NAME, prove_module_program as run_prove_module_program


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:

    @mcp.tool(name=TOOL_NAME)
    def prove_module_program(
        domain_file: str,
        problem_file: str,
        module_program_file: str,
        output_dir: str,
        num_threads: int = 1,
        max_num_states: int = 100_000,
        max_time_seconds: float = 5.0,
        hstar_max_num_states: int = 100_000,
        hstar_max_time_seconds: float = 1.0,
        include_hstar: bool = True,
        include_hlmcut: bool = True,
        max_arity: int = 0,
        max_open_state_counterexamples: int = 1,
        max_deadend_transition_counterexamples: int = 1,
    ) -> dict:
        """Prove an extended Runir module program and write every counterexample separately."""
        return run_prove_module_program(
            ProveModuleProgramOptions(
                domain_file=domain_file,
                problem_file=problem_file,
                module_program_file=module_program_file,
                output_dir=server_output_dir(config.output_root, output_dir).as_posix(),
                num_threads=num_threads,
                max_num_states=max_num_states,
                max_time_seconds=max_time_seconds,
                hstar_max_num_states=hstar_max_num_states,
                hstar_max_time_seconds=hstar_max_time_seconds,
                include_hstar=include_hstar,
                include_hlmcut=include_hlmcut,
                max_arity=max_arity,
                max_open_state_counterexamples=max_open_state_counterexamples,
                max_deadend_transition_counterexamples=max_deadend_transition_counterexamples,
            )
        )
