"""Single-parse context for `execute_policy`.

The policy (base DL), the unsolvability classifier (uns DL), and the grounded task (state repository
+ successor generator) are all built from ONE parse of the domain and share that domain handle. This
is required for the failure-rollout's `classify`: DL symbol indices are per-parse and the uns
evaluation dereferences state-repository data, so a classifier built from a *different* parse (or a
separately grounded task) is a use-after-free / index mismatch against the states the rollout walks.

The `Parser` and lifted task are retained on the context so the single parse's domain/grounding stay
alive for the whole execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir.datasets import GroundTaskSearchContext, LiftedTaskSearchContext
from pyrunir.kr.dl.base.semantics import ConstructorRepositoryFactory as DLConstructorRepositoryFactory
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLConstructorRepositoryFactory
from pyrunir.kr.ps.base import RepositoryFactory as PolicyRepositoryFactory
from pyrunir.kr.uns import Repository as ClassifierRepository, RepositoryFactory as ClassifierRepositoryFactory
from pyrunir_mcp.kr.ps.classifier import build_classifier
from pypddl.formalism import ParserOptions
from pytyr.formalism.planning import Parser, PlanningDomain
from pytyr.planning.lifted import GroundTaskInstantiationOptions, GroundTaskInstantiationStatus, Task as LiftedTask
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedLiftedSearchContext, LoadedSearchContext
from pyrunir_mcp.kr.ps.base.core.features import BasePolicyContext


@dataclass(frozen=True)
class ExecuteContext:
    policy_context: BasePolicyContext
    classifier_repository: ClassifierRepository
    task: LoadedSearchContext
    lifted_task: LoadedLiftedSearchContext
    # Retained so the single parse's domain view (used by every repository) and the grounding behind
    # `task.search_context` stay alive for the whole execution — including the rollout's `classify`.
    parser: Parser
    formal_lifted_task: LiftedTask


def create_execute_context(domain_path: Path, problem_path: Path, execution_context: ExecutionContext) -> ExecuteContext:
    parser = Parser(domain_path, ParserOptions())
    domain = parser.get_domain()
    # Base DL + policy repositories (for the sketch) and the uns DL + classifier repositories (for the
    # classifier) all over THIS one domain handle.
    base_dl_repository = DLConstructorRepositoryFactory().create(domain)
    policy_repository = PolicyRepositoryFactory().create(base_dl_repository)
    policy_context = BasePolicyContext(planning_domain=domain, dl_repository=base_dl_repository, policy_repository=policy_repository)
    classifier_repository = ClassifierRepositoryFactory().create(UnsDLConstructorRepositoryFactory().create(domain))
    # Grounding from the SAME parser → same domain, one state repository + successor generator.
    formalism_task = parser.parse_task(problem_path, ParserOptions())
    lifted_task = LiftedTask(formalism_task)
    lifted_context = LiftedTaskSearchContext(lifted_task, execution_context)
    grounded = lifted_task.instantiate_ground_task(execution_context, GroundTaskInstantiationOptions())
    if grounded.status != GroundTaskInstantiationStatus.SUCCESS:
        raise RuntimeError(f"Grounding failed for {problem_path}: {grounded.status}")
    task = LoadedSearchContext(problem_path=problem_path, search_context=GroundTaskSearchContext(grounded.task, execution_context))
    lifted_task_context = LoadedLiftedSearchContext(problem_path=problem_path, search_context=lifted_context)
    return ExecuteContext(
        policy_context=policy_context,
        classifier_repository=classifier_repository,
        task=task,
        lifted_task=lifted_task_context,
        parser=parser,
        formal_lifted_task=lifted_task,
    )
