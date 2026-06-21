from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir.kr.dl.base.semantics import ConstructorRepository as DLConstructorRepository
from pyrunir.kr.dl.base.semantics import ConstructorRepositoryFactory as DLConstructorRepositoryFactory
from pyrunir.kr.ps.base import GroundSketchProofResults as GroundPolicyProofResults
from pyrunir.kr.ps.base import Repository as PolicyRepository
from pyrunir.kr.ps.base import RepositoryFactory as PolicyRepositoryFactory
from pypddl.formalism import ParserOptions
from pytyr.formalism.planning import Parser, PlanningDomain

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext


@dataclass(frozen=True)
class BasePolicyContext:
    planning_domain: PlanningDomain
    dl_repository: DLConstructorRepository
    policy_repository: PolicyRepository


@dataclass(frozen=True)
class PolicyProofCounterexample:
    task: LoadedSearchContext
    result: GroundPolicyProofResults


@dataclass(frozen=True)
class ExecutionFailure:
    task: LoadedSearchContext
    result: GroundPolicyProofResults


def create_base_policy_context(domain_path: Path) -> BasePolicyContext:
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = DLConstructorRepositoryFactory().create(planning_domain)
    policy_repository = PolicyRepositoryFactory().create(dl_repository)
    return BasePolicyContext(
        planning_domain=planning_domain,
        dl_repository=dl_repository,
        policy_repository=policy_repository,
    )
