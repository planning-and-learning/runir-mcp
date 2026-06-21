from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir.kr.dl.ext import ConstructorRepository as ExtDLConstructorRepository
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtDLConstructorRepositoryFactory
from pyrunir.kr.ps.ext import GroundModuleProgramProofResults as GroundPolicyProofResults
from pyrunir.kr.ps.ext import Repository as PolicyRepository
from pyrunir.kr.ps.ext import RepositoryFactory as PolicyRepositoryFactory
from pypddl.formalism import ParserOptions
from pytyr.formalism.planning import Parser, PlanningDomain

from pyrunir_mcp.kr.ps.ext.core.data_loader import LoadedSearchContext


@dataclass(frozen=True)
class ModuleProgramContext:
    planning_domain: PlanningDomain
    module_output_repository: ExtDLConstructorRepository
    policy_repository: PolicyRepository


@dataclass(frozen=True)
class PolicyProofCounterexample:
    task: LoadedSearchContext
    result: GroundPolicyProofResults


@dataclass(frozen=True)
class ExecutionFailure:
    task: LoadedSearchContext
    result: GroundPolicyProofResults


def create_module_program_context(domain_path: Path) -> ModuleProgramContext:
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    module_output_repository = ExtDLConstructorRepositoryFactory().create(planning_domain)
    policy_repository = PolicyRepositoryFactory().create(module_output_repository)
    return ModuleProgramContext(
        planning_domain=planning_domain,
        module_output_repository=module_output_repository,
        policy_repository=policy_repository,
    )
