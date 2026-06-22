from __future__ import annotations

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.base.schemas import ProveSketchPolicyOptions
from pyrunir_mcp.paths import server_output_dir
from pyrunir_mcp.kr.ps.base.service import TOOL_NAME, prove_sketch_policy as run_prove_sketch_policy


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:

    @mcp.tool(name=TOOL_NAME)
    def prove_sketch_policy(
        domain_file: str,
        problem_file: str,
        sketch_file: str,
        output_dir: str,
        num_threads: int = 1,
        max_num_states: int = 100_000,
        max_time_seconds: float = 5.0,
        max_open_state_counterexamples: int = 1,
        max_deadend_transition_counterexamples: int = 1,
    ) -> dict:
        """Prove a Runir sketch policy and write every counterexample separately."""
        return run_prove_sketch_policy(
            ProveSketchPolicyOptions(
                domain_file=domain_file,
                problem_file=problem_file,
                sketch_file=sketch_file,
                output_dir=server_output_dir(config.output_root, output_dir).as_posix(),
                num_threads=num_threads,
                max_num_states=max_num_states,
                max_time_seconds=max_time_seconds,
                max_open_state_counterexamples=max_open_state_counterexamples,
                max_deadend_transition_counterexamples=max_deadend_transition_counterexamples,
            )
        )
