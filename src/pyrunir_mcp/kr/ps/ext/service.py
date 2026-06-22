from __future__ import annotations

from pathlib import Path
from typing import TypeAlias, cast

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtRepositoryFactory
from pyrunir.kr.ps.ext import (
    CallRule,
    DoRule,
    GroundModuleProgramSearchOptions,
    LoadRule,
    Module,
    ModuleProgram,
    Repository,
    RepositoryFactory,
    SketchRule,
    parse_module_program,
    prove_ground_solution,
)
from pytyr.formalism.planning import Parser, PlanningDomain

from pyrunir_mcp.feature_evidence import Feature, feature_key, state_evidence
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.proof import make_search_options, prove_tasks, write_proof_run

TOOL_NAME = "runir.ps.ext.prove_module_program"


ModuleRule: TypeAlias = LoadRule | SketchRule | DoRule | CallRule


def _iter_module_rules(program: ModuleProgram) -> list[ModuleRule]:
    rules: list[ModuleRule] = []
    for module in program.get_modules():
        for transition in module.get_memory_transitions():
            for rule_variant in transition:
                rules.append(cast(ModuleRule, rule_variant.get_variant()))
    return rules



def _declared_features(value: ModuleProgram | Module) -> list[Feature]:
    features: list[Feature] = []
    features.extend(cast(list[Feature], value.get_concept_features()))
    features.extend(cast(list[Feature], value.get_boolean_features()))
    features.extend(cast(list[Feature], value.get_numerical_features()))
    return features


def _declared_module_program_features(program: ModuleProgram) -> list[Feature]:
    features = _declared_features(program)
    for module in program.get_modules():
        features.extend(_declared_features(module))
    return features


def collect_features(program: ModuleProgram) -> list[Feature]:
    features_by_key: dict[str, Feature] = {}
    for feature in _declared_module_program_features(program):
        features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def prove_module_program(options: ProveModuleProgramOptions) -> JsonObject:
    domain_path = Path(options.domain_file).resolve()
    problem_path = Path(options.problem_file).resolve()
    planning_domain, repository = _repositories(domain_path)
    program = parse_module_program(
        Path(options.module_program_file).read_text(encoding="utf-8"),
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
        problem_path=problem_path,
        num_threads=options.num_threads,
        prove_one=lambda task: prove_ground_solution(task.search_context, program, search_options),
        evidence=state_evidence(features, include_facts=True),
        max_open_state_counterexamples=options.max_open_state_counterexamples,
        max_deadend_transition_counterexamples=options.max_deadend_transition_counterexamples,
    )
    return write_proof_run(
        tool=TOOL_NAME,
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain_file": domain_path.as_posix(),
            "problem_file": problem_path.as_posix(),
            "module_program_file": options.module_program_file,
            "num_threads": options.num_threads,
            "max_num_states": options.max_num_states,
            "max_time_seconds": options.max_time_seconds,
            "max_arity": options.max_arity,
            "max_open_state_counterexamples": options.max_open_state_counterexamples,
            "max_deadend_transition_counterexamples": options.max_deadend_transition_counterexamples,
            "features": [feature_key(feature) for feature in features],
        },
        result=result,
    )
