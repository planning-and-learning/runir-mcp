from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.uns.reformat.service import ReformatClassifierOptions, reformat_classifier
from pyrunir_mcp.paths import server_output_path
from pyrunir_mcp.results import reformat_result

TOOL_NAME = "runir.uns.reformat_classifier"


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    @mcp.tool(name=TOOL_NAME)
    def reformat_unsolvability_classifier(domain: str, classifier_file: str) -> dict[str, Any]:
        """Parse-check and rewrite an unsolvability classifier in canonical form."""
        result = reformat_classifier(
            ReformatClassifierOptions(
                domain_path=Path(domain).resolve(),
                classifier_file=server_output_path(config.output_root, classifier_file),
            )
        )
        return reformat_result(
            tool=TOOL_NAME,
            path_key="classifier_file",
            path=result.classifier_file,
            num_features=result.num_features,
        )
