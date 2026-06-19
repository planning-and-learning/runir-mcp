from __future__ import annotations

from tests.support.artifacts import assert_common_output, read_json, write_example_tool_output


def test_prove_module_program_writes_category_directories_and_feature_values(tmp_path):
    result = write_example_tool_output(
        tmp_path,
        tool="runir.ps.ext.prove_module_program",
        counterexamples=[
            {
                "task": "p-002.pddl",
                "category": "deadend_transition",
                "proof_status": "FAILURE",
                "states": [
                    {
                        "vertex": 1,
                        "state_id": 3,
                        "memory_state": "m0",
                        "feature_values": {"holding": False},
                    },
                    {
                        "vertex": 2,
                        "state_id": 4,
                        "memory_state": "m1",
                        "feature_values": {"holding": True},
                    },
                ],
                "transitions": [{"edge": 7, "source": 1, "target": 2}],
            }
        ],
    )

    run_dir = tmp_path / "run"
    summary = assert_common_output(run_dir, result, expected_count=1)
    item = summary["by_category"]["deadend_transition"]["items"][0]
    assert item["task"] == "p-002.pddl"
    assert item["path"] == "counterexamples/deadend_transition/deadend_transition-001.json"
    assert item["trace_path"] == "traces/deadend_transition/deadend_transition-001.json"
    assert item["trace_available"] is True

    counterexample = read_json(run_dir / item["path"])
    trace = read_json(run_dir / item["trace_path"])
    assert counterexample["trace_path"] == item["trace_path"]
    assert trace["states"][1]["memory_state"] == "m1"
    assert trace["states"][1]["feature_values"] == {"holding": True}
