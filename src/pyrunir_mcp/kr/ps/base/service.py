from __future__ import annotations

from pathlib import Path
from typing import Any

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.base.cnf_grammar import ConstructorRepositoryFactory as CNFRepositoryFactory
from pyrunir.kr.dl.base.cnf_grammar import translate
from pyrunir.kr.dl.base.grammar import (
    ConstructorRepositoryFactory as GrammarRepositoryFactory,
    GrammarFactory,
    GrammarSpecification,
)
from pyrunir.kr.dl.base.semantics import ConstructorRepositoryFactory as SemanticsRepositoryFactory
from pyrunir.kr.ps.base import GroundSketchSearchOptions, RepositoryFactory, prove_ground_solution
from pyrunir.kr.ps.base.dl import SketchFactory, parse_sketch
from pytyr.formalism.planning import Parser

from pyrunir_mcp.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.base.schemas import ProveSketchPolicyOptions
from pyrunir_mcp.proof import make_search_options, prove_tasks, write_proof_run

TOOL_NAME = "runir.ps.base.prove_sketch_policy"


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    domain = planning_domain.get_domain()
    grammar_repository = GrammarRepositoryFactory().create(planning_domain)
    source_grammar = GrammarFactory.create(
        GrammarSpecification.FRANCE_ET_AL_AAAI2021,
        domain,
        grammar_repository,
    )
    cnf_repository = CNFRepositoryFactory().create(planning_domain)
    translate(source_grammar, cnf_repository)
    semantics_repository = SemanticsRepositoryFactory().create(planning_domain)
    policy_repository = RepositoryFactory().create(semantics_repository)
    return planning_domain, policy_repository


def _variant_feature(variant: object) -> object | None:
    concrete = variant
    for _ in range(2):
        get_variant = getattr(concrete, "get_variant", None)
        if not callable(get_variant):
            break
        concrete = get_variant()
    get_feature = getattr(concrete, "get_feature", None)
    return get_feature() if callable(get_feature) else None


def collect_features(policy: object) -> list[object]:
    get_features = getattr(policy, "get_features", None)
    if not callable(get_features):
        return []
    features_by_key: dict[str, object] = {}
    for feature in get_features():
        features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def prove_sketch_policy(options: ProveSketchPolicyOptions) -> dict[str, Any]:
    domain_path = Path(options.domain).resolve()
    train_path = Path(options.train_dir).resolve()
    planning_domain, repository = _repositories(domain_path)
    if options.policy_file is None:
        policy = SketchFactory.create_empty(repository)
    else:
        policy = parse_sketch(Path(options.policy_file).read_text(encoding="utf-8"), planning_domain, repository)
    features = collect_features(policy)
    search_options = make_search_options(
        GroundSketchSearchOptions(),
        options.max_num_states,
        options.max_time_seconds,
    )

    result = prove_tasks(
        domain_path=domain_path,
        train_dir=train_path,
        num_threads=options.num_threads,
        prove_one=lambda task: prove_ground_solution(task.search_context, policy, search_options),
        evidence=state_evidence(features, include_facts=options.dump_state_mode in {"facts", "full"}),
    )
    return write_proof_run(
        tool=TOOL_NAME,
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain": domain_path.as_posix(),
            "train_dir": train_path.as_posix(),
            "policy_file": options.policy_file,
            "num_threads": options.num_threads,
            "max_num_states": options.max_num_states,
            "max_time_seconds": options.max_time_seconds,
            "dump_state_mode": options.dump_state_mode,
            "features": [feature_key(feature) for feature in features],
        },
        result=result,
    )
