from __future__ import annotations

from pyrunir.kr.ps.base import GroundSketchSearchOptions as PolicySearchOptions, Sketch as Policy, find_ground_solution

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext
from pyrunir_mcp.kr.ps.base.core.features import ExecutionFailure
from pyrunir_mcp.kr.ps.status import is_success_status


def execute_policy_on_tasks(
    policy: Policy,
    execute_tasks: list[LoadedSearchContext],
    options: PolicySearchOptions | None = None,
) -> ExecutionFailure | None:
    num_tasks = len(execute_tasks)
    search_options = options or PolicySearchOptions()

    for index, task in enumerate(execute_tasks, start=1):
        result = find_ground_solution(task.search_context, policy, search_options)
        print(f"[{index}/{num_tasks}] {task.problem_path.name}: {result.status.name}", flush=True)
        if not is_success_status(result.status):
            return ExecutionFailure(task=task, result=result)

    return None
