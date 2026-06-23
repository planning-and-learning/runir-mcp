from __future__ import annotations

from typing import TypeAlias

from pyrunir.kr.ps.ext import GroundModuleProgramSearchOptions as GroundPolicySearchOptions, ModuleProgram as Policy, ModuleProgramProofStatus as PolicyProofStatus, find_ground_solution
from pytyr.planning import SearchStatus

from pyrunir_mcp.kr.ps.ext.core.data_loader import LoadedSearchContext
from pyrunir_mcp.kr.ps.ext.core.features import ExecutionFailure


PolicyStatus: TypeAlias = PolicyProofStatus | SearchStatus


def is_success_status(status: PolicyStatus) -> bool:
    return status.name in {"SOLVED", "SUCCESS"}


def execute_policy_on_tasks(
    policy: Policy,
    execute_tasks: list[LoadedSearchContext],
    options: GroundPolicySearchOptions | None = None,
) -> ExecutionFailure | None:
    num_tasks = len(execute_tasks)
    search_options = options or GroundPolicySearchOptions()

    for index, task in enumerate(execute_tasks, start=1):
        result = find_ground_solution(task.search_context, policy, search_options)
        print(f"[{index}/{num_tasks}] {task.problem_path.name}: {result.status.name}", flush=True)
        if not is_success_status(result.status):
            return ExecutionFailure(task=task, result=result)

    return None
