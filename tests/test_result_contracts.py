from __future__ import annotations

import json
from pathlib import Path

from pyrunir_mcp.results import execute_result, reformat_result
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
    assert result["prompt_summary"]["category_counts"] == {
        "false_negative": 1,
        "false_positive": 2,
    }
    assert result["prompt_summary"]["classifier_semantics"] == {
        "true": "predicted unsolvable",
        "false": "predicted solvable",
        "false_positive": "true on a solvable state",
        "false_negative": "false on an unsolvable state",
    }
    assert "items" not in result["prompt_summary"]
    assert [item["path"] for item in result["items"]] == [
        "counterexamples/false_positive/false_positive-001.json",
        "counterexamples/false_positive/false_positive-002.json",
        "counterexamples/false_negative/false_negative-003.json",
    ]
    for item in result["items"]:
        assert (tmp_path / "run" / item["path"]).is_file()


def test_write_summary_refuses_existing_summary_json(tmp_path):
    import pytest
    from pyrunir_mcp.artifacts import CommandResult, write_summary

    output_dir = tmp_path / "run"
    output_dir.mkdir()
    (output_dir / "summary.json").write_text("stale\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_summary(
            tool="runir.uns.prove_classifier",
            status="success",
            output_dir=output_dir,
            command=CommandResult(args=[], cwd=tmp_path, returncode=0, stdout="out", stderr="err"),
            metadata={},
            counterexamples=[],
        )

    assert (output_dir / "summary.json").read_text(encoding="utf-8") == "stale\n"


def test_reformat_result_uses_layered_contract(tmp_path):
    policy = tmp_path / "sketch.txt"
    policy.write_text("(:sketch)", encoding="utf-8")

    result = reformat_result(
        tool="runir.ps.base.reformat_policy",
        path_key="sketch_file",
        path=policy,
        kind="sketch",
    )

    assert result["status"] == "success"
    assert result["primary"]["successful"] is True
    assert result["primary"]["sketch_file"] == "sketch.txt"
    assert result["primary"]["kind"] == "sketch"
    assert result["primary"]["prompt_summary"] == result["prompt_summary"]
    assert result["prompt_summary"] == {
        "tool": "runir.ps.base.reformat_policy",
        "status": "success",
        "successful": True,
        "artifacts": {"sketch_file": "sketch.txt"},
        "kind": "sketch",
    }
    assert result["summary"]["tool"] == "runir.ps.base.reformat_policy"
    assert result["artifacts"]["sketch_file"] == "sketch.txt"
    assert result["sketch_file"] == "sketch.txt"
    assert result["items"] == []


def test_counterexample_category_slug_removes_path_segments(tmp_path):
    result = write_example_tool_output(
        tmp_path,
        tool="runir.uns.prove_classifier",
        counterexamples=[{"task": "p1.pddl", "category": "../bad/name"}],
    )

    assert result["items"][0]["category"] == "bad_name"
    assert result["items"][0]["path"] == "counterexamples/bad_name/bad_name-001.json"
    assert (tmp_path / "run" / "counterexamples" / "bad_name" / "bad_name-001.json").is_file()
    assert not (tmp_path / "bad").exists()


def test_reused_counterexample_output_allocates_child_run(tmp_path):
    first = write_example_tool_output(
        tmp_path,
        tool="runir.uns.prove_classifier",
        counterexamples=[{"task": "p1.pddl", "category": "false_positive"}],
    )
    second = write_example_tool_output(
        tmp_path,
        tool="runir.uns.prove_classifier",
        counterexamples=[{"task": "p2.pddl", "category": "false_negative"}],
    )

    assert first["output_dir"].endswith("/run")
    assert second["output_dir"].endswith("/run/run-002")
    assert (tmp_path / "run" / "summary.json").is_file()
    assert (tmp_path / "run" / "run-002" / "summary.json").is_file()


def test_existing_counterexample_tree_forces_child_run(tmp_path):
    from pyrunir_mcp.artifacts import fresh_output_dir

    output_dir = tmp_path / "run"
    stale_tree = output_dir / "counterexamples" / "open_state"
    stale_tree.mkdir(parents=True)
    (stale_tree / "old.json").write_text("{}\n", encoding="utf-8")

    fresh = fresh_output_dir(output_dir)

    assert fresh == output_dir / "run-002"
    assert (stale_tree / "old.json").is_file()
    assert (output_dir / "run-002" / ".pyrunir-mcp-output").is_file()



def test_existing_traces_tree_forces_child_run(tmp_path):
    from pyrunir_mcp.artifacts import fresh_output_dir

    output_dir = tmp_path / "run"
    stale_tree = output_dir / "traces" / "open_state"
    stale_tree.mkdir(parents=True)
    (stale_tree / "old.json").write_text("{}\n", encoding="utf-8")

    fresh = fresh_output_dir(output_dir)

    assert fresh == output_dir / "run-002"
    assert (stale_tree / "old.json").is_file()
    assert (output_dir / "run-002" / ".pyrunir-mcp-output").is_file()

def test_partial_execute_output_forces_child_run(tmp_path):
    from pyrunir_mcp.artifacts import fresh_output_dir

    output_dir = tmp_path / "execute"
    failures = output_dir / "failures"
    failures.mkdir(parents=True)
    (output_dir / "manifest.json").write_text('{"tasks": []}\n', encoding="utf-8")
    (failures / "task-001.json").write_text("{}\n", encoding="utf-8")

    fresh = fresh_output_dir(output_dir)

    assert fresh == output_dir / "run-002"
    assert (output_dir / "manifest.json").read_text(encoding="utf-8") == '{"tasks": []}\n'
    assert (failures / "task-001.json").is_file()
    assert (output_dir / "run-002" / ".pyrunir-mcp-output").is_file()


def test_fresh_output_dir_reserves_empty_directory(tmp_path):
    from pyrunir_mcp.artifacts import fresh_output_dir

    output_dir = tmp_path / "run"
    output_dir.mkdir()

    first = fresh_output_dir(output_dir)
    second = fresh_output_dir(output_dir)

    assert first == output_dir
    assert second == output_dir / "run-002"
    assert (output_dir / ".pyrunir-mcp-output").is_file()
    assert (output_dir / "run-002" / ".pyrunir-mcp-output").is_file()


def test_execute_cli_reused_output_allocates_child_run(monkeypatch, tmp_path):
    from pyrunir_mcp import invoke

    class Result:
        failure = None

    calls: list[Path] = []

    def fake_execute(options):
        dump_dir = Path(options.dump_dir)
        calls.append(dump_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / "manifest.json").write_text(
            '{"tasks": [], "distinct_failures": []}\n',
            encoding="utf-8",
        )
        (dump_dir / "summary.md").write_text("# summary\n", encoding="utf-8")
        return Result()

    monkeypatch.setattr(invoke, "execute_base_policy", fake_execute)
    output_dir = tmp_path / "execute"
    args = {
        "domain_file": str(tmp_path / "domain.pddl"),
        "problem_file": str(tmp_path / "problem.pddl"),
        "sketch_file": str(tmp_path / "sketch.txt"),
        "output_dir": str(output_dir),
    }

    first = invoke._base_execute(invoke.Args(args))
    second = invoke._base_execute(invoke.Args(args))

    assert calls == [output_dir, output_dir / "run-002"]
    assert first["output_dir"] == output_dir.as_posix()
    assert second["output_dir"] == (output_dir / "run-002").as_posix()
    assert (output_dir / "manifest.json").is_file()
    assert (output_dir / "run-002" / "manifest.json").is_file()


def test_execute_result_relativizes_absolute_trace_paths_inside_output_dir(tmp_path):
    class Result:
        failure = object()

    output_dir = tmp_path / "execute" / "run-002"
    output_dir.mkdir(parents=True)
    trace = output_dir / "trace_seed-0.json"
    trace.write_text(json.dumps({"states": [{"state_index": 1, "feature_values": {"n": 1}}], "transitions": []}) + "\n", encoding="utf-8")
    manifest = {
        "tasks": [
            {
                "problem_file": "p1.pddl",
                "status": "FAILED",
                "failure_category": "open_state",
                "seed": 0,
                "trace_file": trace.as_posix(),
            }
        ],
        "distinct_failures": [
            {
                "problem_file": "p1.pddl",
                "failure_category": "open_state",
                "seed": 0,
                "trace_file": trace.as_posix(),
            }
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    result = execute_result(tool="runir.ps.base.execute_policy", result=Result(), output_dir=output_dir)

    assert result["tasks"][0]["trace_path"] == "trace_seed-0.json"
    assert result["items"][0]["path"] == "counterexamples/open_state/open_state-001.json"
    assert result["items"][0]["trace_path"] is None
    assert result["items"][0]["trace_available"] is False
    assert (output_dir / result["items"][0]["path"]).is_file()
    counterexample = json.loads((output_dir / result["items"][0]["path"]).read_text(encoding="utf-8"))
    assert counterexample["state"]["feature_values"] == {"n": 1}
    assert result["manifest"]["tasks"][0]["trace_file"] == "trace_seed-0.json"
    assert result["manifest"]["distinct_failures"][0]["trace_file"] == "trace_seed-0.json"
    persisted = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert persisted["tasks"][0]["trace_file"] == trace.as_posix()


def test_execute_result_promotes_only_representative_failures(tmp_path):
    class Result:
        failure = object()

    output_dir = tmp_path / "execute"
    output_dir.mkdir()
    (output_dir / "trace_seed-0.json").write_text(
        json.dumps({"states": [{"state_index": 1, "feature_values": {"n": 1}}], "transitions": []}) + "\n",
        encoding="utf-8",
    )
    (output_dir / "trace_seed-1.json").write_text("{}\n", encoding="utf-8")
    (output_dir / "trace_seed-2.json").write_text(
        json.dumps({
            "states": [{"state_index": 1}, {"state_index": 2}, {"state_index": 1}],
            "transitions": [
                {"step": 0, "source_state_index": 1, "target_state_index": 2, "action": "a"},
                {"step": 1, "source_state_index": 2, "target_state_index": 1, "action": "b"},
            ],
            "cycle": {"prefix_state_indices": [], "cycle_state_indices": [1, 2, 1], "prefix_transition_steps": [], "cycle_transition_steps": [0, 1]},
        }) + "\n",
        encoding="utf-8",
    )
    (output_dir / "trace_seed-3.json").write_text(
        json.dumps({"states": [{"state_index": 4, "feature_values": {"n": 4}}], "transitions": []}) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "tasks": [
            {
                "problem_file": "p1.pddl",
                "status": "FAILED",
                "failure_category": "open_state",
                "seed": 0,
                "trace_file": "trace_seed-0.json",
            },
            {
                "problem_file": "p1.pddl",
                "status": "FAILED",
                "failure_category": "open_state",
                "seed": 1,
                "trace_file": "trace_seed-1.json",
            },
            {
                "problem_file": "p1.pddl",
                "status": "FAILED",
                "failure_category": "cycle",
                "seed": 2,
                "trace_file": "trace_seed-2.json",
            },
            {
                "problem_file": "p2.pddl",
                "status": "FAILED",
                "failure_category": "open_state",
                "seed": 3,
                "trace_file": "trace_seed-3.json",
            },
        ],
        "distinct_failures": [
            {
                "problem_file": "p1.pddl",
                "failure_category": "open_state",
                "seed": 0,
                "trace_file": "trace_seed-0.json",
                "fingerprint": "p1-open",
            },
            {
                "problem_file": "p1.pddl",
                "failure_category": "cycle",
                "seed": 2,
                "trace_file": "trace_seed-2.json",
                "fingerprint": "p1-cycle",
            },
            {
                "problem_file": "p2.pddl",
                "failure_category": "open_state",
                "seed": 3,
                "trace_file": "trace_seed-3.json",
                "fingerprint": "p2-open",
            },
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    result = execute_result(tool="runir.ps.base.execute_policy", result=Result(), output_dir=output_dir)

    assert [(item["task"], item["failure_category"]) for item in result["items"]] == [
        ("p1.pddl", "open_state"),
        ("p1.pddl", "cycle"),
        ("p2.pddl", "open_state"),
    ]
    assert [item["path"] for item in result["items"]] == [
        "counterexamples/open_state/open_state-001.json",
        "counterexamples/cycle/cycle-002.json",
        "counterexamples/open_state/open_state-003.json",
    ]
    assert [item["trace_path"] for item in result["items"]] == [
        None,
        "traces/cycle/cycle-002.json",
        None,
    ]
    cycle_counterexample = json.loads((output_dir / result["items"][1]["path"]).read_text(encoding="utf-8"))
    cycle_trace = json.loads((output_dir / result["items"][1]["trace_path"]).read_text(encoding="utf-8"))
    assert cycle_counterexample["cycle"]["cycle_state_indices"] == [1, 2, 1]
    assert [transition["action"] for transition in cycle_counterexample["transitions"]] == ["a", "b"]
    assert [transition["action"] for transition in cycle_trace["transitions"]] == []
    assert result["primary"]["failure_count"] == 3
    assert result["prompt_summary"]["counts"]["failures"] == 3


def test_execute_result_omits_absolute_trace_paths_outside_output_dir(tmp_path):
    class Result:
        failure = object()

    output_dir = tmp_path / "execute"
    output_dir.mkdir()
    trace = tmp_path / "outside" / "trace_seed-0.json"
    trace.parent.mkdir()
    trace.write_text("{}\n", encoding="utf-8")
    manifest = {
        "tasks": [
            {
                "problem_file": "p1.pddl",
                "status": "FAILED",
                "failure_category": "open_state",
                "seed": 0,
                "trace_file": trace.as_posix(),
            }
        ],
        "distinct_failures": [
            {
                "problem_file": "p1.pddl",
                "failure_category": "open_state",
                "seed": 0,
                "trace_file": trace.as_posix(),
            }
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    result = execute_result(tool="runir.ps.base.execute_policy", result=Result(), output_dir=output_dir)

    assert result["tasks"][0]["trace_path"] == "<omitted: outside output_dir>"
    assert result["items"][0]["path"] == "counterexamples/open_state/open_state-001.json"
    assert result["items"][0]["trace_path"] is None
    assert result["items"][0]["trace_available"] is False
    assert (output_dir / result["items"][0]["path"]).is_file()
    assert result["manifest"]["tasks"][0]["trace_file"] == "<omitted: outside output_dir>"
    assert result["manifest"]["distinct_failures"][0]["trace_file"] == "<omitted: outside output_dir>"


def test_base_execute_cli_passes_trace_metadata_options(monkeypatch, tmp_path):
    from pyrunir_mcp import invoke

    class Result:
        failure = None

    seen = {}

    def fake_execute(options):
        seen.update({
            "max_arity": options.max_arity,
            "dump_max_steps": options.dump_max_steps,
            "dump_max_states": options.dump_max_states,
        })
        dump_dir = Path(options.dump_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / "manifest.json").write_text(
            '{"tasks": [], "distinct_failures": []}\n',
            encoding="utf-8",
        )
        (dump_dir / "summary.md").write_text("# summary\n", encoding="utf-8")
        return Result()

    monkeypatch.setattr(invoke, "execute_base_policy", fake_execute)
    result = invoke._base_execute(invoke.Args({
        "domain_file": str(tmp_path / "domain.pddl"),
        "problem_file": str(tmp_path / "problem.pddl"),
        "sketch_file": str(tmp_path / "sketch.txt"),
        "output_dir": str(tmp_path / "execute"),
        "max_arity": 1,
        "dump_max_steps": 7,
        "dump_max_states": 13,
    }))

    assert seen == {
        "max_arity": 1,
        "dump_max_steps": 7,
        "dump_max_states": 13,
    }
    assert result["primary"]["successful"] is True


def test_ext_execute_cli_passes_resource_budget(monkeypatch, tmp_path):
    from pyrunir_mcp import invoke

    class Result:
        failure = None

    seen = {}

    def fake_execute(options):
        seen["max_arity"] = options.max_arity
        seen["max_num_states"] = options.max_num_states
        seen["max_time_seconds"] = options.max_time_seconds
        dump_dir = Path(options.dump_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / "manifest.json").write_text(
            '{"tasks": [], "distinct_failures": []}\n',
            encoding="utf-8",
        )
        (dump_dir / "summary.md").write_text("# summary\n", encoding="utf-8")
        return Result()

    monkeypatch.setattr(invoke, "execute_ext_policy", fake_execute)
    result = invoke._ext_execute(invoke.Args({
        "domain_file": str(tmp_path / "domain.pddl"),
        "problem_file": str(tmp_path / "problem.pddl"),
        "module_program_file": str(tmp_path / "module_program.txt"),
        "output_dir": str(tmp_path / "execute"),
        "max_arity": 2,
        "max_num_states": 123,
        "max_time_seconds": 4.5,
    }))

    assert seen == {"max_arity": 2, "max_num_states": 123, "max_time_seconds": 4.5}
    assert result["primary"]["successful"] is True
