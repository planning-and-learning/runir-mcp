from __future__ import annotations

from pathlib import Path
from typing import Any

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtRepositoryFactory
from pyrunir.kr.ps.ext import (
    GroundModuleProgramSearchOptions,
    RepositoryFactory,
    parse_module_program,
    prove_ground_solution,
)
from pytyr.formalism.planning import Parser

from pyrunir_mcp.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.proof import make_search_options, prove_tasks, write_proof_run

TOOL_NAME = "runir.ps.ext.prove_module_program"


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = ExtRepositoryFactory().create(planning_domain)
    program_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, program_repository


def _rule_feature_variants(rule: object) -> list[object]:
    variants: list[object] = []
    get_conditions = getattr(rule, "get_conditions", None)
    if callable(get_conditions):
        variants.extend(get_conditions())
    get_effects = getattr(rule, "get_effects", None)
    if callable(get_effects):
        variants.extend(get_effects())
    return variants


def _variant_feature(variant: object) -> object | None:
    concrete = variant
    for _ in range(2):
        get_variant = getattr(concrete, "get_variant", None)
        if not callable(get_variant):
            break
        concrete = get_variant()
    get_feature = getattr(concrete, "get_feature", None)
    return get_feature() if callable(get_feature) else None


def _iter_module_rules(program: object) -> list[object]:
    get_modules = getattr(program, "get_modules", None)
    if not callable(get_modules):
        return []
    rules: list[object] = []
    for module in get_modules():
        transitions = getattr(module, "get_memory_transitions", None)
        if not callable(transitions):
            continue
        for transition in transitions():
            for rule_variant in transition:
                get_variant = getattr(rule_variant, "get_variant", None)
                rules.append(get_variant() if callable(get_variant) else rule_variant)
    return rules


def collect_features(program: object) -> list[object]:
    features_by_key: dict[str, object] = {}
    get_rules = getattr(program, "get_rules", None)
    rules = list(get_rules()) if callable(get_rules) else _iter_module_rules(program)
    for rule in rules:
        for variant in _rule_feature_variants(rule):
            feature = _variant_feature(variant)
            if feature is not None:
                features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def prove_module_program(options: ProveModuleProgramOptions) -> dict[str, Any]:
    domain_path = Path(options.domain).resolve()
    train_path = Path(options.train_dir).resolve()
    planning_domain, repository = _repositories(domain_path)
    program = parse_module_program(
        Path(options.module_program_file).read_text(),
        planning_domain,
        repository,
    )
    features = collect_features(program)
    search_options = make_search_options(
        GroundModuleProgramSearchOptions(),
        options.max_num_states,
        options.max_time_seconds,
    )
    search_options.max_arity = options.max_arity

    result = prove_tasks(
        domain_path=domain_path,
        train_dir=train_path,
        num_threads=options.num_threads,
        prove_one=lambda task: prove_ground_solution(task.search_context, program, search_options),
        evidence=state_evidence(features, include_facts=options.dump_state_mode in {"facts", "full"}),
    )
    return write_proof_run(
        tool=TOOL_NAME,
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain": domain_path.as_posix(),
            "train_dir": train_path.as_posix(),
            "module_program_file": options.module_program_file,
            "num_threads": options.num_threads,
            "max_num_states": options.max_num_states,
            "max_time_seconds": options.max_time_seconds,
            "max_arity": options.max_arity,
            "dump_state_mode": options.dump_state_mode,
            "features": [feature_key(feature) for feature in features],
        },
        result=result,
    )
