from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pyrunir.kr.ps.base import GroundSketchProofResults as GroundPolicyProofResults
from pyrunir.kr.dl.base import cnf_grammar
from pyrunir.kr.dl.base.grammar import (
    ConstructorRepository as GrammarConstructorRepository,
    ConstructorRepositoryFactory as GrammarConstructorRepositoryFactory,
)
from pyrunir.kr.dl.base.grammar import (
    GrammarFactory,
    GrammarSpecification,
)
from pyrunir.kr.dl.base.semantics import ConstructorRepository as DLConstructorRepository
from pyrunir.kr.dl.base.semantics import ConstructorRepositoryFactory as DLConstructorRepositoryFactory
from pyrunir.kr.ps.base import Repository as PolicyRepository
from pyrunir.kr.ps.base import RepositoryFactory as PolicyRepositoryFactory
from pytyr.formalism.planning import Parser, ParserOptions, PlanningDomain

from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext


@dataclass(frozen=True)
class FranceDLFeatureGenerator:
    planning_domain: PlanningDomain
    grammar_repository: GrammarConstructorRepository
    cnf_repository: cnf_grammar.ConstructorRepository
    output_repository: DLConstructorRepository
    policy_repository: PolicyRepository
    grammar: cnf_grammar.Grammar


@dataclass(frozen=True)
class PolicyProofCounterexample:
    task: LoadedSearchContext
    result: GroundPolicyProofResults


@dataclass(frozen=True)
class ExecutionFailure:
    task: LoadedSearchContext
    result: GroundPolicyProofResults


def create_france_dl_feature_generator(domain_path: Path) -> FranceDLFeatureGenerator:
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    domain = planning_domain.get_domain()

    grammar_repository = GrammarConstructorRepositoryFactory().create(planning_domain)
    source_grammar = GrammarFactory.create(GrammarSpecification.FRANCE_ET_AL_AAAI2021, domain, grammar_repository)

    cnf_repository = cnf_grammar.ConstructorRepositoryFactory().create(planning_domain)
    grammar = cnf_grammar.translate(source_grammar, cnf_repository)

    output_repository = DLConstructorRepositoryFactory().create(planning_domain)
    policy_repository = PolicyRepositoryFactory().create(output_repository)
    return FranceDLFeatureGenerator(
        planning_domain=planning_domain,
        grammar_repository=grammar_repository,
        cnf_repository=cnf_repository,
        output_repository=output_repository,
        policy_repository=policy_repository,
        grammar=grammar,
    )


