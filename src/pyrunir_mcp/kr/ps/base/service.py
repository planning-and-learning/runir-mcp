from __future__ import annotations

from pathlib import Path

from pyrunir.kr.ps.base import GroundSketchSearchOptions, Sketch, prove_ground_solution

from pyrunir_mcp.feature_evidence import Feature, feature_key, state_evidence
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.base.core.features import create_base_policy_context
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description
from pyrunir_mcp.kr.ps.base.schemas import ProveSketchPolicyOptions
from pyrunir_mcp.proof import make_search_options, prove_tasks, write_proof_run

TOOL_NAME = "runir.ps.base.prove_sketch_policy"



def collect_features(policy: Sketch) -> list[Feature]:
    features_by_key: dict[str, Feature] = {}
    for feature in policy.get_boolean_features():
        features_by_key.setdefault(feature_key(feature), feature)
    for feature in policy.get_numerical_features():
        features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def prove_sketch_policy(options: ProveSketchPolicyOptions) -> JsonObject:
    domain_path = Path(options.domain_file).resolve()
    problem_path = Path(options.problem_file).resolve()
    context = create_base_policy_context(domain_path)
    description = Path(options.sketch_file).read_text(encoding="utf-8")
    policy = parse_policy_description(context, description)
    features = collect_features(policy)
    search_options = make_search_options(
        GroundSketchSearchOptions(),
        options.max_num_states,
        options.max_time_seconds,
    )

    result = prove_tasks(
        domain_path=domain_path,
        problem_path=problem_path,
        num_threads=options.num_threads,
        prove_one=lambda task: prove_ground_solution(task.search_context, policy, search_options),
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
            "sketch_file": options.sketch_file,
            "num_threads": options.num_threads,
            "max_num_states": options.max_num_states,
            "max_time_seconds": options.max_time_seconds,
            "max_open_state_counterexamples": options.max_open_state_counterexamples,
            "max_deadend_transition_counterexamples": options.max_deadend_transition_counterexamples,
            "features": [feature_key(feature) for feature in features],
        },
        result=result,
    )
