from __future__ import annotations

from pathlib import Path

from pyrunir.kr.ps.ext import (
    GroundModuleProgramSearchOptions,
    parse_module_program,
    prove_ground_solution,
)
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.kr.ps.classifier import build_classifier, classifier_evidence
from pyrunir_mcp.kr.ps.ext.core.execute_context import create_execute_context
from pyrunir_mcp.kr.ps.ext.rules import collect_features, intern_rules
from pyrunir_mcp.kr.ps.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HStarOptions
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.kr.ps.frontier import make_ext_frontier_expander
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.kr.ps.proof import build_proof_run, make_search_options

TOOL_NAME = "runir.ps.ext.prove_module_program"


def prove_module_program(options: ProveModuleProgramOptions) -> JsonObject:
    domain_path = Path(options.domain_file).resolve()
    problem_path = Path(options.problem_file).resolve()
    context = create_execute_context(domain_path, problem_path, ExecutionContext(options.num_threads))
    program = parse_module_program(
        Path(options.module_program_file).read_text(encoding="utf-8"),
        context.module_program_context.planning_domain,
        context.module_program_context.policy_repository,
    )
    features = collect_features(program)
    search_options = make_search_options(GroundModuleProgramSearchOptions(), options.max_num_states, options.max_time_seconds)
    search_options.max_arity = options.max_arity

    task = context.task
    hstar_task = context.lifted_task if options.include_hstar or options.include_hlmcut else None
    result = prove_ground_solution(task.search_context, program, search_options)

    dicts = Dictionaries(ext=True)
    intern_rules(program, dicts)

    hstar = None
    if hstar_task is not None:
        hstar = HStarEvaluator(hstar_task.search_context, HStarOptions(options.hstar_max_num_states, options.hstar_max_time_seconds))
    evidence = state_evidence(
        features,
        include_facts=True,
        hstar=hstar,
        include_hstar=options.include_hstar,
        include_hlmcut=options.include_hlmcut,
    )
    classifier = None
    if options.classifier_file is not None:
        classifier = build_classifier(context.classifier_repository, context.module_program_context.planning_domain, Path(options.classifier_file))
    evidence = classifier_evidence(evidence, classifier)
    return build_proof_run(
        tool=TOOL_NAME,
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain_file": domain_path.as_posix(),
            "problem_file": problem_path.as_posix(),
            "module_program_file": options.module_program_file,
            "classifier_file": options.classifier_file,
            "num_threads": options.num_threads,
            "max_num_states": options.max_num_states,
            "max_time_seconds": options.max_time_seconds,
            "hstar_max_num_states": options.hstar_max_num_states,
            "hstar_max_time_seconds": options.hstar_max_time_seconds,
            "include_hstar": options.include_hstar,
            "include_hlmcut": options.include_hlmcut,
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
        include_hstar=options.include_hstar,
        include_hlmcut=options.include_hlmcut,
    )
