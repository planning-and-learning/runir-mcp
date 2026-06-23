from __future__ import annotations

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.uns.schemas import ProveClassifierOptions
from pyrunir_mcp.paths import server_output_dir
from pyrunir_mcp.kr.uns.service import TOOL_NAME, prove_classifier as run_prove_classifier


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:

    @mcp.tool(name=TOOL_NAME)
    def prove_classifier(
        domain_file: str,
        problem_file: str,
        output_dir: str,
        classifier_file: str,
        max_num_states: int = 1_000_000,
        max_time_seconds: float = 1_000_000_000.0,
        max_false_positive_counterexamples: int = 20,
        max_false_negative_counterexamples: int = 20,
    ) -> dict:
        """Prove an unsolvability DNF classifier and write each counterexample separately."""
        return run_prove_classifier(
            ProveClassifierOptions(
                domain_file=domain_file,
                problem_file=problem_file,
                output_dir=server_output_dir(config.output_root, output_dir).as_posix(),
                classifier_file=classifier_file,
                max_num_states=max_num_states,
                max_time_seconds=max_time_seconds,
                max_false_positive_counterexamples=max_false_positive_counterexamples,
                max_false_negative_counterexamples=max_false_negative_counterexamples,
            )
        )
