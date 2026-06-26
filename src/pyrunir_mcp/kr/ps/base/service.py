from __future__ import annotations

from pathlib import Path

from pyrunir.kr.ps.base import GroundSketchSearchOptions, prove_ground_solution
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.kr.ps.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HStarOptions
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.base.core.features import collect_features, create_base_policy_context, intern_rules
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description
from pyrunir_mcp.kr.ps.base.schemas import ProvePolicyOptions
from pyrunir_mcp.kr.ps.frontier import make_frontier_expander
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.planning import load_grounded_search_context, load_lifted_search_context
from pyrunir_mcp.kr.ps.proof import build_proof_run, make_search_options

TOOL_NAME = "runir.ps.base.prove_policy"


def prove_policy(options: ProvePolicyOptions) -> JsonObject:
    domain_path = Path(options.domain_file).resolve()
    problem_path = Path(options.problem_file).resolve()
    context = create_base_policy_context(domain_path)
    policy = parse_policy_description(context, Path(options.sketch_file).read_text(encoding="utf-8"))
    features = collect_features(policy)
    search_options = make_search_options(GroundSketchSearchOptions(), options.max_num_states, options.max_time_seconds)

    execution_context = ExecutionContext(options.num_threads)
    task = load_grounded_search_context(domain_path, problem_path, execution_context)
    hstar_task = load_lifted_search_context(domain_path, problem_path, execution_context)
    result = prove_ground_solution(task.search_context, policy, search_options)

    hstar = HStarEvaluator(hstar_task.search_context, HStarOptions(options.hstar_max_num_states, options.hstar_max_time_seconds))
    evidence = state_evidence(features, include_facts=True, hstar=hstar)
    dicts = Dictionaries(ext=False)
    intern_rules(policy, dicts)
    return build_proof_run(
        tool=TOOL_NAME,
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain_file": domain_path.as_posix(),
            "problem_file": problem_path.as_posix(),
            "sketch_file": options.sketch_file,
            "num_threads": options.num_threads,
            "max_num_states": options.max_num_states,
            "max_time_seconds": options.max_time_seconds,
            "hstar_max_num_states": options.hstar_max_num_states,
            "hstar_max_time_seconds": options.hstar_max_time_seconds,
            "max_open_state_counterexamples": options.max_open_state_counterexamples,
            "max_deadend_transition_counterexamples": options.max_deadend_transition_counterexamples,
        },
        task=task,
        result=result,
        feature_symbols=[feature_key(feature) for feature in features],
        dicts=dicts,
        ext=False,
        evidence=evidence,
        expander=make_frontier_expander(task.search_context, policy, evidence),
        max_open_state_counterexamples=options.max_open_state_counterexamples,
        max_deadend_transition_counterexamples=options.max_deadend_transition_counterexamples,
    )
