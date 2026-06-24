from __future__ import annotations

from pathlib import Path
from fastmcp import FastMCP

from pyrunir_mcp.artifacts import fresh_output_dir
from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.base.execute.service import ExecutePolicyOptions, ExecutePolicyResult, execute_policy
from pyrunir_mcp.paths import server_output_dir
from pyrunir_mcp.results import execute_result

TOOL_NAME = "runir.ps.base.execute_policy"


def _result_payload(result: ExecutePolicyResult, output_dir: Path) -> JsonObject:
    return execute_result(tool=TOOL_NAME, result=result, output_dir=output_dir)


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:

    @mcp.tool(name=TOOL_NAME)
    def execute_base_policy(
        domain_file: str,
        problem_file: str,
        sketch_file: str,
        output_dir: str,
        classifier_file: str | None = None,
        num_threads: int = 1,
        random_seed: int = 0,
        random_seed_start: int = 0,
        num_rollouts: int = 1,
        shuffle_labeled_succ_nodes: bool = True,
        max_arity: int = 0,
        max_num_states: int | None = None,
        max_time_seconds: float | None = None,
    ) -> dict:
        """Execute a base Runir sketch policy and write traces/manifests.

        `classifier_file` is an optional unsolvability classifier used to flag dead states in the
        failure trace; when omitted, the empty classifier is used (no state marked unsolvable).
        """
        resolved_output_dir = fresh_output_dir(server_output_dir(config.output_root, output_dir))
        result = execute_policy(
            ExecutePolicyOptions(
                domain_file=Path(domain_file).resolve(),
                problem_file=Path(problem_file).resolve(),
                sketch_file=Path(sketch_file).resolve(),
                classifier_file=Path(classifier_file).resolve() if classifier_file else None,
                num_threads=num_threads,
                random_seed=random_seed,
                random_seed_start=random_seed_start,
                num_rollouts=num_rollouts,
                shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
                max_arity=max_arity,
                max_num_states=max_num_states,
                max_time_seconds=max_time_seconds,
                dump_dir=resolved_output_dir,
            )
        )
        return _result_payload(result, resolved_output_dir)
