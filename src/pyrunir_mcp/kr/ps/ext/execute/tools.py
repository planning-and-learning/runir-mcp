from __future__ import annotations

from pathlib import Path
from fastmcp import FastMCP

from pyrunir_mcp.artifacts import fresh_output_dir
from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.ext.execute.service import ExecutePolicyOptions, ExecutePolicyResult, execute_policy
from pyrunir_mcp.paths import server_output_dir
from pyrunir_mcp.results import execute_result

TOOL_NAME = "runir.ps.ext.execute_module_program"


def _result_payload(result: ExecutePolicyResult, output_dir: Path) -> dict:
    return execute_result(tool=TOOL_NAME, result=result, output_dir=output_dir)


def register_tools(mcp: FastMCP, config: ServerConfig) -> None:

    @mcp.tool(name=TOOL_NAME)
    def execute_module_program(
        domain: str,
        problem_dir: str,
        module_program_file: str,
        output_dir: str,
        num_threads: int = 1,
        random_seed: int = 0,
        random_seed_start: int = 0,
        num_rollouts: int = 1,
        shuffle_labeled_succ_nodes: bool = True,
        max_arity: int = 0,
        max_num_states: int | None = None,
        max_time: float | None = None,
        dump_state_mode: str = "summary",
        dump_max_steps: int | None = None,
        dump_max_compatible_actions: int | None = None,
        dump_max_states: int | None = None,
        audit_compatible_successors: bool = False,
        classify_compatible_successors: bool = False,
        classifier: str = "astar",
        classifier_max_time: float = 1.0,
        classifier_max_states: int = 10_000,
        include_policy_metadata: bool = False,
        replay_trace: str | None = None,
    ) -> dict:
        """Execute an extended Runir module program and write traces/manifests."""
        resolved_output_dir = fresh_output_dir(server_output_dir(config.output_root, output_dir))
        result = execute_policy(
            ExecutePolicyOptions(
                domain_path=Path(domain).resolve(),
                problem_dir=Path(problem_dir).resolve(),
                module_program_file=Path(module_program_file).resolve(),
                num_threads=num_threads,
                random_seed=random_seed,
                random_seed_start=random_seed_start,
                num_rollouts=num_rollouts,
                shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
                max_arity=max_arity,
                max_num_states=max_num_states,
                max_time=max_time,
                dump_dir=resolved_output_dir,
                dump_state_mode=dump_state_mode,  # type: ignore[arg-type]
                dump_max_steps=dump_max_steps,
                dump_max_compatible_actions=dump_max_compatible_actions,
                dump_max_states=dump_max_states,
                audit_compatible_successors=audit_compatible_successors,
                classify_compatible_successors=classify_compatible_successors,
                classifier=classifier,  # type: ignore[arg-type]
                classifier_max_time=classifier_max_time,
                classifier_max_states=classifier_max_states,
                include_policy_metadata=include_policy_metadata,
                replay_trace=None if replay_trace is None else Path(replay_trace).resolve(),
            )
        )
        return _result_payload(result, resolved_output_dir)
