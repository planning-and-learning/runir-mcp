from __future__ import annotations


from pyrunir_mcp.results import reformat_result
from tests.support.artifacts import write_example_tool_output


def test_counterexample_result_exposes_primary_category_counts(tmp_path):
    result = write_example_tool_output(
        tmp_path,
        tool="runir.uns.prove_classifier",
        counterexamples=[
            {"task": "p1.pddl", "category": "false_positive"},
            {"task": "p2.pddl", "category": "false_positive"},
            {"task": "p3.pddl", "category": "false_negative"},
        ],
    )

    assert result["primary"]["successful"] is False
    assert result["primary"]["category_counts"] == {
        "false_negative": 1,
        "false_positive": 2,
    }
    assert result["primary"]["counterexample_count"] == 3
    assert [item["path"] for item in result["items"]] == [
        "counterexamples/false_positive/false_positive-001.json",
        "counterexamples/false_positive/false_positive-002.json",
        "counterexamples/false_negative/false_negative-003.json",
    ]


def test_reformat_result_uses_layered_contract(tmp_path):
    policy = tmp_path / "policy.txt"
    policy.write_text("(:sketch)", encoding="utf-8")

    result = reformat_result(
        tool="runir.ps.base.reformat_policy",
        path_key="policy_file",
        path=policy,
        kind="sketch",
    )

    assert result["status"] == "success"
    assert result["primary"] == {
        "successful": True,
        "policy_file": policy.as_posix(),
        "kind": "sketch",
    }
    assert result["summary"]["tool"] == "runir.ps.base.reformat_policy"
    assert result["artifacts"]["policy_file"] == policy.as_posix()
    assert result["items"] == []
