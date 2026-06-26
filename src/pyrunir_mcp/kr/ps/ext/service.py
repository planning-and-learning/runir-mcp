from __future__ import annotations

from pathlib import Path

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtRepositoryFactory
from pyrunir.kr.ps.ext import (
    GroundModuleProgramSearchOptions,
    RepositoryFactory,
    parse_module_program,
    prove_ground_solution,
)
from pytyr.formalism.planning import Parser
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.kr.ps.ext.rules import collect_features, intern_rules
from pyrunir_mcp.kr.ps.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HStarOptions
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.kr.ps.frontier import make_ext_frontier_expander
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.planning import load_grounded_search_context, load_lifted_search_context
from pyrunir_mcp.kr.ps.proof import build_proof_run, make_search_options

TOOL_NAME = "runir.ps.ext.prove_module_program"


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = ExtRepositoryFactory().create(planning_domain)
    program_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, program_repository


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
    hstar_task = load_lifted_search_context(domain_path, problem_path, execution_context)
    result = prove_ground_solution(task.search_context, program, search_options)

    dicts = Dictionaries(ext=True)
    intern_rules(program, dicts)

    hstar = HStarEvaluator(hstar_task.search_context, HStarOptions(options.hstar_max_num_states, options.hstar_max_time_seconds))
    evidence = state_evidence(features, include_facts=True, hstar=hstar)
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
            "hstar_max_num_states": options.hstar_max_num_states,
            "hstar_max_time_seconds": options.hstar_max_time_seconds,
            "max_arity": options.max_arity,
            "max_open_state_counterexamples": options.max_open_state_counterexamples,
            "max_deadend_transition_counterexamples": options.max_deadend_transition_counterexamples,
        },
        task=task,
        result=result,
        feature_symbols=[feature_key(feature) for feature in features],
        dicts=dicts,
        ext=True,
        evidence=evidence,
        expander=make_ext_frontier_expander(task.search_context, program, evidence),
        max_open_state_counterexamples=options.max_open_state_counterexamples,
        max_deadend_transition_counterexamples=options.max_deadend_transition_counterexamples,
    )
