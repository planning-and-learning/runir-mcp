from __future__ import annotations

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.base.schemas import ProvePolicyOptions
from pyrunir_mcp.paths import server_output_dir
from pyrunir_mcp.kr.ps.base.service import TOOL_NAME, prove_policy as run_prove_policy


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:

    @mcp.tool(name=TOOL_NAME)
    def prove_policy(
        domain_file: str,
        problem_file: str,
        sketch_file: str,
        output_dir: str,
        classifier_file: str | None = None,
        num_threads: int = 1,
        max_num_states: int = 100_000,
        max_time_seconds: float = 5.0,
        hstar_max_num_states: int = 100_000,
        hstar_max_time_seconds: float = 1.0,
        include_hstar: bool = True,
        include_hlmcut: bool = True,
        max_open_state_counterexamples: int = 1,
        max_deadend_transition_counterexamples: int = 1,
    ) -> dict:
        """Prove a Runir sketch policy and write every counterexample separately."""
        return run_prove_policy(
            ProvePolicyOptions(
                domain_file=domain_file,
                problem_file=problem_file,
                sketch_file=sketch_file,
                output_dir=server_output_dir(config.output_root, output_dir).as_posix(),
                classifier_file=classifier_file,
                num_threads=num_threads,
                max_num_states=max_num_states,
                max_time_seconds=max_time_seconds,
                hstar_max_num_states=hstar_max_num_states,
                hstar_max_time_seconds=hstar_max_time_seconds,
                include_hstar=include_hstar,
                include_hlmcut=include_hlmcut,
                max_open_state_counterexamples=max_open_state_counterexamples,
                max_deadend_transition_counterexamples=max_deadend_transition_counterexamples,
            )
        )
