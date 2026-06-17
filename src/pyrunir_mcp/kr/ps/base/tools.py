from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.base.schemas import ProveSketchPolicyOptions
from pyrunir_mcp.kr.ps.base.service import TOOL_NAME, prove_sketch_policy as run_prove_sketch_policy


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    del config

    @mcp.tool(name=TOOL_NAME)
    def prove_sketch_policy(
        domain: str,
        train_dir: str,
        output_dir: str,
        policy_file: str | None = None,
        num_threads: int = 1,
        max_num_states: int = 100_000,
        max_time_seconds: float = 5.0,
        dump_state_mode: str = "summary",
    ) -> dict[str, Any]:
        """Prove a Runir sketch policy and write every counterexample separately."""
        return run_prove_sketch_policy(
            ProveSketchPolicyOptions(
                domain=domain,
                train_dir=train_dir,
                output_dir=output_dir,
                policy_file=policy_file,
                num_threads=num_threads,
                max_num_states=max_num_states,
                max_time_seconds=max_time_seconds,
                dump_state_mode=dump_state_mode,
            )
        )
