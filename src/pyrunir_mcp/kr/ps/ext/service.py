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
    RepositoryFactory,
    SketchRule,
    parse_module_program,
    prove_ground_solution,
)
from pytyr.formalism.planning import Parser
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.kr.ps.feature_evidence import Feature, feature_key, state_evidence
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.planning import load_grounded_search_context
from pyrunir_mcp.kr.ps.proof import build_proof_run, make_search_options

TOOL_NAME = "runir.ps.ext.prove_module_program"

ModuleRule: TypeAlias = LoadRule | SketchRule | DoRule | CallRule


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = ExtRepositoryFactory().create(planning_domain)
    program_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, program_repository


def _iter_module_rules(program: ModuleProgram) -> list[tuple[Module, ModuleRule]]:
    rules: list[tuple[Module, ModuleRule]] = []
    for module in program.get_modules():
        for transition in module.get_memory_transitions():
            for rule_variant in transition:
                rules.append((module, cast(ModuleRule, rule_variant.get_variant())))
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


def _intern_rules(program: ModuleProgram, dicts: Dictionaries) -> None:
    """Populate the run-global rules dictionary (symbol -> src/tgt memory) up front, in policy
    order, so transition rows can resolve `rK` and ext rules carry their memory transition."""
    for module, rule in _iter_module_rules(program):
        symbol = str(rule.get_symbol()).strip()
        if not symbol:
            continue
        module_name = str(module.get_name())
        source = dicts.memory(module_name, str(rule.get_source().get_name()), "")
        target = dicts.memory(module_name, str(rule.get_target().get_name()), "")
        dicts.rule(symbol, source, target)


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
    search_options = make_search_options(GroundModuleProgramSearchOptions(), options.max_num_states, options.max_time_seconds)
    search_options.max_arity = options.max_arity

    execution_context = ExecutionContext(options.num_threads)
    task = load_grounded_search_context(domain_path, problem_path, execution_context)
    result = prove_ground_solution(task.search_context, program, search_options)

    dicts = Dictionaries(ext=True)
    _intern_rules(program, dicts)

    return build_proof_run(
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
        },
        task=task,
        result=result,
        feature_symbols=[feature_key(feature) for feature in features],
        dicts=dicts,
        ext=True,
        evidence=state_evidence(features, include_facts=True),
        max_open_state_counterexamples=options.max_open_state_counterexamples,
        max_deadend_transition_counterexamples=options.max_deadend_transition_counterexamples,
    )
