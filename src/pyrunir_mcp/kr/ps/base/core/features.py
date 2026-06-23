from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir.kr.dl.base.semantics import ConstructorRepository as DLConstructorRepository
from pyrunir.kr.dl.base.semantics import ConstructorRepositoryFactory as DLConstructorRepositoryFactory
from pyrunir.kr.ps.base import GroundSketchProofResults as GroundPolicyProofResults
from pyrunir.kr.ps.base import Repository as PolicyRepository
from pyrunir.kr.ps.base import RepositoryFactory as PolicyRepositoryFactory
from pyrunir.kr.ps.base import Sketch
from pypddl.formalism import ParserOptions
from pytyr.formalism.planning import Parser, PlanningDomain

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext
from pyrunir_mcp.kr.ps.feature_evidence import Feature, feature_key


@dataclass(frozen=True)
class BasePolicyContext:
    planning_domain: PlanningDomain
    dl_repository: DLConstructorRepository
    policy_repository: PolicyRepository


@dataclass(frozen=True)
class ExecutionFailure:
    task: LoadedSearchContext
    result: GroundPolicyProofResults


def collect_features(policy: Sketch) -> list[Feature]:
    features_by_key: dict[str, Feature] = {}
    for feature in policy.get_boolean_features():
        features_by_key.setdefault(feature_key(feature), feature)
    for feature in policy.get_numerical_features():
        features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def create_base_policy_context(domain_path: Path) -> BasePolicyContext:
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = DLConstructorRepositoryFactory().create(planning_domain)
    policy_repository = PolicyRepositoryFactory().create(dl_repository)
    return BasePolicyContext(
        planning_domain=planning_domain,
        dl_repository=dl_repository,
        policy_repository=policy_repository,
    )
