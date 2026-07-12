from __future__ import annotations

from pyrunir.kr.ps.base import GroundSketchSearchOptions as PolicySearchOptions
from pyrunir.kr.ps.base import Sketch as Policy
from pyrunir.kr.ps.base import find_ground_solution

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext
from pyrunir_mcp.kr.ps.base.core.features import ExecutionFailure
from pyrunir_mcp.kr.ps.proof import is_goal_open_state_result
from pyrunir_mcp.kr.ps.status import is_success_status


def execute_policy_on_tasks(
    policy: Policy,
    execute_tasks: list[LoadedSearchContext],
    options: PolicySearchOptions | None = None,
) -> ExecutionFailure | None:
    search_options = options or PolicySearchOptions()

    for task in execute_tasks:
        result = find_ground_solution(task.task_context, policy, search_options)
        if not is_success_status(result.status) and not is_goal_open_state_result(result):
            return ExecutionFailure(task=task, result=result)

    return None
