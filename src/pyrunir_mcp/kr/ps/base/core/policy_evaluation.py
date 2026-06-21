from __future__ import annotations

from typing import TypeAlias

from pyrunir.kr.ps.base import GroundSketchSearchOptions as GroundPolicySearchOptions, Sketch as Policy, SketchProofStatus as PolicyProofStatus, find_ground_solution, prove_ground_solution
from pytyr.planning import SearchStatus

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext
from pyrunir_mcp.kr.ps.base.core.features import PolicyProofCounterexample, ExecutionFailure


PolicyStatus: TypeAlias = PolicyProofStatus | SearchStatus


def is_success_status(status: PolicyStatus) -> bool:
    return getattr(status, "name", str(status)) in {"SOLVED", "SUCCESS"}


def failure_category_from_status(status: PolicyStatus) -> str | None:
    name = getattr(status, "name", str(status))
    return None if name in {"SOLVED", "SUCCESS"} else name.lower()


def sort_by_problem_name(tasks: list[LoadedSearchContext]) -> list[LoadedSearchContext]:
    return sorted(tasks, key=lambda task: task.problem_path.name)


def prove_policy_on_training_tasks(
    policy: Policy,
    train_tasks: list[LoadedSearchContext],
    options: GroundPolicySearchOptions | None = None,
) -> list[PolicyProofCounterexample]:
    counterexamples = []
    proof_options = options or GroundPolicySearchOptions()
    num_tasks = len(train_tasks)

    for index, task in enumerate(train_tasks, start=1):
        result = prove_ground_solution(task.search_context, policy, proof_options)
        print(
            f"[{index}/{num_tasks}] {task.problem_path.name}: {result.status.name} "
            f"(deadends={len(result.deadend_transitions)}, open={len(result.open_states)}, cycle={len(result.cycle)})",
            flush=True,
        )
        if result.status != PolicyProofStatus.SUCCESS:
            counterexamples.append(PolicyProofCounterexample(task=task, result=result))

    return counterexamples


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
