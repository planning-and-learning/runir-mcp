"""Single-parse domain/task contexts for base policy execute/prove."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir.datasets import GroundTaskSearchContext, LiftedTaskSearchContext
from pyrunir.kr.dl.base.semantics import (
    ConstructorRepositoryFactory as DLConstructorRepositoryFactory,
)
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtDLConstructorRepositoryFactory
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLConstructorRepositoryFactory
from pyrunir.kr.ps.base import RepositoryFactory as PolicyRepositoryFactory
from pyrunir.kr.ps.ext import RepositoryFactory as ModuleRepositoryFactory
from pyrunir.kr.uns import (
    RepositoryFactory as ClassifierRepositoryFactory,
)
from pypddl.formalism import ParserOptions
from pyyggdrasil.execution import ExecutionContext
from pytyr.formalism.planning import Parser
from pytyr.planning.lifted import (
    GroundTaskInstantiationOptions,
    GroundTaskInstantiationStatus,
    Task as LiftedTask,
)

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedLiftedSearchContext, LoadedSearchContext
from pyrunir_mcp.kr.ps.base.core.features import BasePolicyContext
from pyrunir_mcp.kr.ps.classifier import ClassifierContext
from pyrunir_mcp.kr.ps.ext.core.features import ModuleProgramContext


@dataclass
class DomainContext:
    policy_context: BasePolicyContext
    module_program_context: ModuleProgramContext
    classifier_context: ClassifierContext
    parser: Parser
    next_task_index: int = 1


@dataclass(frozen=True)
class TaskContext:
    id: str
    index: int
    domain_context: DomainContext
    task: LoadedSearchContext
    lifted_task: LoadedLiftedSearchContext

    @property
    def policy_context(self) -> BasePolicyContext:
        return self.domain_context.policy_context

    @property
    def module_program_context(self) -> ModuleProgramContext:
        return self.domain_context.module_program_context

    @property
    def classifier_context(self) -> ClassifierContext:
        return self.domain_context.classifier_context

    @property
    def parser(self) -> Parser:
        return self.domain_context.parser


def create_domain_context(domain_path: Path) -> DomainContext:
    parser = Parser(domain_path, ParserOptions())
    domain = parser.get_domain()
    base_dl_repository = DLConstructorRepositoryFactory().create(domain)
    policy_repository = PolicyRepositoryFactory().create(base_dl_repository)
    policy_context = BasePolicyContext(
        planning_domain=domain,
        dl_repository=base_dl_repository,
        policy_repository=policy_repository,
    )
    ext_repository = ExtDLConstructorRepositoryFactory().create(domain)
    module_repository = ModuleRepositoryFactory().create(ext_repository)
    module_program_context = ModuleProgramContext(
        planning_domain=domain,
        module_output_repository=ext_repository,
        policy_repository=module_repository,
    )
    classifier_context = ClassifierContext(
        planning_domain=domain,
        classifier_repository=ClassifierRepositoryFactory().create(
            UnsDLConstructorRepositoryFactory().create(domain)
        ),
    )
    return DomainContext(
        policy_context=policy_context,
        module_program_context=module_program_context,
        classifier_context=classifier_context,
        parser=parser,
    )


def create_task_context(
    domain_context: DomainContext, problem_path: Path, execution_context: ExecutionContext
) -> TaskContext:
    index = domain_context.next_task_index
    domain_context.next_task_index += 1
    formalism_task = domain_context.parser.parse_task(problem_path, ParserOptions())
    lifted_task = LiftedTask(formalism_task)
    lifted_context = LiftedTaskSearchContext(lifted_task, execution_context)
    grounded = lifted_task.instantiate_ground_task(
        execution_context, GroundTaskInstantiationOptions()
    )
    if grounded.status != GroundTaskInstantiationStatus.SUCCESS:
        raise RuntimeError(f"Grounding failed for {problem_path}: {grounded.status}")
    task = LoadedSearchContext(
        problem_path=problem_path,
        search_context=GroundTaskSearchContext(grounded.task, execution_context),
    )
    lifted_task_context = LoadedLiftedSearchContext(
        problem_path=problem_path, search_context=lifted_context
    )
    return TaskContext(
        id=f"task_{index:06d}",
        index=index,
        domain_context=domain_context,
        task=task,
        lifted_task=lifted_task_context,
    )
