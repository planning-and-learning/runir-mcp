from __future__ import annotations

from pathlib import Path
from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.uns.reformat.service import CreateEmptyClassifierOptions, ReformatClassifierOptions, create_empty_classifier, reformat_classifier
from pyrunir_mcp.paths import server_output_path
from pyrunir_mcp.results import reformat_result

TOOL_NAME = "runir.uns.reformat_classifier"
CREATE_EMPTY_TOOL_NAME = "runir.uns.create_empty_classifier"


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:
    @mcp.tool(name=TOOL_NAME)
    def reformat_unsolvability_classifier(domain_file: str, classifier_file: str) -> dict:
        """Parse-check and rewrite an unsolvability classifier in canonical form."""
        result = reformat_classifier(
            ReformatClassifierOptions(
                domain_path=Path(domain_file).resolve(),
                classifier_file=server_output_path(config.output_root, classifier_file),
            )
        )
        return reformat_result(
            tool=TOOL_NAME,
            path_key="classifier_file",
            path=result.classifier_file,
            num_features=result.num_features,
        )

    @mcp.tool(name=CREATE_EMPTY_TOOL_NAME)
    def create_empty_unsolvability_classifier(classifier_file: str) -> dict:
        """Write the canonical empty unsolvability classifier."""
        result = create_empty_classifier(
            CreateEmptyClassifierOptions(
                classifier_file=server_output_path(config.output_root, classifier_file),
            )
        )
        return reformat_result(
            tool=CREATE_EMPTY_TOOL_NAME,
            path_key="classifier_file",
            path=result.classifier_file,
            num_features=result.num_features,
        )
