from __future__ import annotations

from pathlib import Path
from tests.support.artifacts import assert_common_output, read_json, write_example_tool_output


def test_prove_sketch_policy_writes_hierarchical_counterexample_summary(tmp_path):
    result = write_example_tool_output(
        tmp_path,
        tool="runir.ps.base.prove_sketch_policy",
        counterexamples=[
            {
                "task": "p-001.pddl",
                "category": "open_state",
                "proof_status": "FAILURE",
                "states": [
                    {
                        "vertex_index": 4,
                        "state_index": 9,
                        "feature_values": {"n0": 2, "b0": False},
                    }
                ],
                "transitions": [],
            }
        ],
    )

    run_dir = tmp_path / "run"
    summary = assert_common_output(run_dir, result, expected_count=1)
    item = summary["by_category"]["open_state"]["items"][0]
    assert Path(item["path"]).relative_to(run_dir).as_posix() == "counterexamples/open_state/open_state-001.json"
    assert Path(item["trace_path"]).relative_to(run_dir).as_posix() == "traces/open_state/open_state-001.json"
    assert item["trace_available"] is True

    counterexample = read_json(run_dir / item["path"])
    assert counterexample["id"] == "open_state-001"
    assert counterexample["trace_available"] is True
    assert counterexample["state"]["feature_values"] == {"b0": False, "n0": 2}
    trace = read_json(run_dir / item["trace_path"])
    assert trace["trace_available"] is True
    assert trace["transitions"] == []
    assert trace["states"][0]["feature_values"] == {"b0": False, "n0": 2}
