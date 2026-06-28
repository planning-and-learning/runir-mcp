from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir.datasets import GroundTaskSearchContext, LiftedTaskSearchContext
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtDLConstructorRepositoryFactory
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLConstructorRepositoryFactory
from pyrunir.kr.ps.ext import RepositoryFactory as PolicyRepositoryFactory
from pyrunir.kr.uns import Repository as ClassifierRepository, RepositoryFactory as ClassifierRepositoryFactory
from pypddl.formalism import ParserOptions
from pytyr.formalism.planning import Parser
from pytyr.planning.lifted import GroundTaskInstantiationOptions, GroundTaskInstantiationStatus, Task as LiftedTask
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.kr.ps.ext.core.data_loader import LoadedLiftedSearchContext, LoadedSearchContext
from pyrunir_mcp.kr.ps.ext.core.features import ModuleProgramContext


@dataclass(frozen=True)
class ExecuteContext:
    module_program_context: ModuleProgramContext
    classifier_repository: ClassifierRepository
    task: LoadedSearchContext
    lifted_task: LoadedLiftedSearchContext
    parser: Parser
    formal_lifted_task: LiftedTask


def create_execute_context(domain_path: Path, problem_path: Path, execution_context: ExecutionContext) -> ExecuteContext:
    parser = Parser(domain_path, ParserOptions())
    domain = parser.get_domain()
    ext_repository = ExtDLConstructorRepositoryFactory().create(domain)
    policy_repository = PolicyRepositoryFactory().create(ext_repository)
    module_program_context = ModuleProgramContext(
        planning_domain=domain,
        module_output_repository=ext_repository,
        policy_repository=policy_repository,
    )
    classifier_repository = ClassifierRepositoryFactory().create(UnsDLConstructorRepositoryFactory().create(domain))
    formalism_task = parser.parse_task(problem_path, ParserOptions())
    lifted_task = LiftedTask(formalism_task)
    lifted_context = LiftedTaskSearchContext(lifted_task, execution_context)
    grounded = lifted_task.instantiate_ground_task(execution_context, GroundTaskInstantiationOptions())
    if grounded.status != GroundTaskInstantiationStatus.SUCCESS:
        raise RuntimeError(f"Grounding failed for {problem_path}: {grounded.status}")
    task = LoadedSearchContext(problem_path=problem_path, search_context=GroundTaskSearchContext(grounded.task, execution_context))
    return ExecuteContext(
        module_program_context=module_program_context,
        classifier_repository=classifier_repository,
        task=task,
        lifted_task=LoadedLiftedSearchContext(problem_path=problem_path, search_context=lifted_context),
        parser=parser,
        formal_lifted_task=lifted_task,
    )
