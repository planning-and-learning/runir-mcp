from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.uns.schemas import ProveClassifierOptions
from pyrunir_mcp.kr.uns.service import TOOL_NAME, prove_classifier as run_prove_classifier


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    del config

    @mcp.tool(name=TOOL_NAME)
    def prove_classifier(
        domain: str,
        train_dir: str,
        output_dir: str,
        classifier_file: str | None = None,
        max_num_states: int = 1_000_000,
        max_time_seconds: float = 1_000_000_000.0,
    ) -> dict[str, Any]:
        """Prove an unsolvability DNF classifier and write each counterexample separately."""
        return run_prove_classifier(
            ProveClassifierOptions(
                domain=domain,
                train_dir=train_dir,
                output_dir=output_dir,
                classifier_file=classifier_file,
                max_num_states=max_num_states,
                max_time_seconds=max_time_seconds,
            )
        )
