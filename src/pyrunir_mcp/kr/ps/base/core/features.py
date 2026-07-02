from __future__ import annotations

from dataclasses import dataclass
from pyrunir.kr.dl.base.semantics import ConstructorRepository as DLConstructorRepository
from pyrunir.kr.ps.base import GroundSketchProofResults as PolicyProofResults
from pyrunir.kr.ps.base import Repository as PolicyRepository
from pyrunir.kr.ps.base import Sketch
from pytyr.formalism.planning import PlanningDomain

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext
from pyrunir_mcp.kr.ps.feature_evidence import Feature, feature_key
from pyrunir_mcp.output.dictionaries import Dictionaries


@dataclass(frozen=True)
class BasePolicyContext:
    planning_domain: PlanningDomain
    dl_repository: DLConstructorRepository
    policy_repository: PolicyRepository


@dataclass(frozen=True)
class ExecutionFailure:
    task: LoadedSearchContext
    result: PolicyProofResults


def intern_rules(policy: Sketch, dicts: Dictionaries) -> None:
    """Populate the run-global rules dictionary (by symbol) up front, in policy order, so every
    sketch rule is listed even when a given witness only exercises some of them (mirrors how
    features are interned up front, and how the ext family interns its module rules)."""
    for rule in policy.get_rules():
        symbol = str(rule.get_symbol()).strip()
        if symbol:
            dicts.rule(symbol)


def collect_features(policy: Sketch) -> list[Feature]:
    features_by_key: dict[str, Feature] = {}
    for feature in policy.get_boolean_features():
        features_by_key.setdefault(feature_key(feature), feature)
    for feature in policy.get_numerical_features():
        features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())

