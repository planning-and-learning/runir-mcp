from __future__ import annotations

from pathlib import Path
from typing import Any

from pyrunir.kr.ps.base import GroundSketchSearchOptions, prove_ground_solution

from pyrunir_mcp.feature_evidence import feature_key, state_evidence
from pyrunir_mcp.kr.ps.base.core.features import create_base_policy_context
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description
from pyrunir_mcp.kr.ps.base.schemas import ProveSketchPolicyOptions
from pyrunir_mcp.proof import make_search_options, prove_tasks, write_proof_run

TOOL_NAME = "runir.ps.base.prove_sketch_policy"



def collect_features(policy: object) -> list[object]:
    features_by_key: dict[str, object] = {}
    for getter_name in ("get_boolean_features", "get_numerical_features"):
        get_features = getattr(policy, getter_name, None)
        if not callable(get_features):
            continue
        for feature in get_features():
            features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def prove_sketch_policy(options: ProveSketchPolicyOptions) -> dict[str, Any]:
    domain_path = Path(options.domain).resolve()
    train_path = Path(options.train_dir).resolve()
    context = create_base_policy_context(domain_path)
    description = None if options.policy_file is None else Path(options.policy_file).read_text(encoding="utf-8")
    policy = parse_policy_description(context, description)
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
