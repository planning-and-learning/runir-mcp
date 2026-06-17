from __future__ import annotations

from tests.support.artifacts import assert_common_output, read_json, write_example_tool_output


def test_prove_classifier_writes_all_classifier_counterexamples_separately(tmp_path):
    result = write_example_tool_output(
        tmp_path,
        tool="runir.uns.prove_classifier",
        counterexamples=[
            {
                "task": "p-003.pddl",
                "category": "false_positive",
                "state_id": 12,
                "predicted_unsolvable": True,
                "actually_solvable": True,
                "feature_values": {"deadend_like": True},
                "fluent_facts": ["(at truck loc1)"],
            },
            {
                "task": "p-003.pddl",
                "category": "false_negative",
                "state_id": 13,
                "predicted_unsolvable": False,
                "actually_solvable": False,
                "feature_values": {"deadend_like": False},
                "fluent_facts": ["(at truck loc2)"],
            },
        ],
    )

    run_dir = tmp_path / "run"
    summary = assert_common_output(run_dir, result, expected_count=2)
    assert summary["by_category"]["false_positive"]["count"] == 1
    assert summary["by_category"]["false_negative"]["count"] == 1
    assert summary["counts"]["tasks_with_counterexamples"] == 1

    fp_item = summary["by_category"]["false_positive"]["items"][0]
    fn_item = summary["by_category"]["false_negative"]["items"][0]
    fp = read_json(run_dir / fp_item["path"])
    fn = read_json(run_dir / fn_item["path"])
    assert fp["feature_values"] == {"deadend_like": True}
    assert fn["feature_values"] == {"deadend_like": False}
