from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.uns.reformat.service import ReformatClassifierOptions, reformat_classifier

TOOL_NAME = "runir.uns.reformat_classifier"


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    del config

    @mcp.tool(name=TOOL_NAME)
    def reformat_unsolvability_classifier(domain: str, classifier_file: str) -> dict[str, Any]:
        """Parse-check and rewrite an unsolvability classifier in canonical form."""
        result = reformat_classifier(
            ReformatClassifierOptions(
                domain_path=Path(domain).resolve(),
                classifier_file=Path(classifier_file).resolve(),
            )
        )
        return {
            "status": "success",
            "classifier_file": result.classifier_file.as_posix(),
            "num_features": result.num_features,
        }
