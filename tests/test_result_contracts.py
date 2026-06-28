from __future__ import annotations

import json
from pathlib import Path

from pyrunir_mcp.results import execute_result, reformat_result


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
    assert result["primary"]["sketch_file"] == policy.as_posix()
    assert result["primary"]["kind"] == "sketch"
    assert result["primary"]["prompt_summary"] == result["prompt_summary"]
    assert result["prompt_summary"] == {
        "tool": "runir.ps.base.reformat_policy",
        "status": "success",
        "successful": True,
        "artifacts": {"sketch_file": policy.as_posix()},
        "kind": "sketch",
    }
    assert result["summary"]["tool"] == "runir.ps.base.reformat_policy"
    assert result["artifacts"]["sketch_file"] == policy.as_posix()
    assert result["sketch_file"] == policy.as_posix()
    assert result["items"] == []


def test_existing_failures_tree_forces_child_run(tmp_path):
    from pyrunir_mcp.artifacts import fresh_output_dir

    output_dir = tmp_path / "run"
    stale_tree = output_dir / "failures" / "open_state-001"
    stale_tree.mkdir(parents=True)
    (stale_tree / "meta.json").write_text("{}\n", encoding="utf-8")

    fresh = fresh_output_dir(output_dir)

    assert fresh == output_dir / "run-002"
    assert (stale_tree / "meta.json").is_file()
    assert (output_dir / "run-002" / ".pyrunir-mcp-output").is_file()



def test_existing_dicts_tree_forces_child_run(tmp_path):
    from pyrunir_mcp.artifacts import fresh_output_dir

    output_dir = tmp_path / "run"
    stale_tree = output_dir / "dicts"
    stale_tree.mkdir(parents=True)
    (stale_tree / "features.psv").write_text("id|symbol\n", encoding="utf-8")

    fresh = fresh_output_dir(output_dir)

    assert fresh == output_dir / "run-002"
    assert (stale_tree / "features.psv").is_file()
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



def test_execute_result_reuses_service_written_failure_artifacts(tmp_path):
    class Result:
        failure = object()

    output_dir = tmp_path / "execute"
    failure_dir = output_dir / "failures" / "open_state-001"
    witness_path = failure_dir / "witness.json"
    trace_path = failure_dir / "trace.json"
    meta_path = failure_dir / "meta.json"
    failure_dir.mkdir(parents=True)
    witness_path.write_text(json.dumps({"schema_version": 1, "id": "open_state-001"}) + "\n", encoding="utf-8")
    trace_path.write_text(json.dumps({"schema_version": 1, "id": "open_state-001", "states": []}) + "\n", encoding="utf-8")
    meta_path.write_text(json.dumps({"id": "open_state-001", "category": "open_state"}) + "\n", encoding="utf-8")
    successors_path = failure_dir / "successors.psv"
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "problem_file": "p1.pddl",
                        "status": "FAILURE",
                        "failure_category": "open_state",
                        "seed": 0,
                        "trace_path": trace_path.as_posix(),
                    }
                ],
                "distinct_failures": [
                    {
                        "problem_file": "p1.pddl",
                        "task": "p1.pddl",
                        "status": "FAILURE",
                        "failure_category": "open_state",
                        "seed": 0,
                        "witness_path": witness_path.as_posix(),
                        "trace_path": trace_path.as_posix(),
                        "successors_path": successors_path.as_posix(),
                        "meta_path": meta_path.as_posix(),
                        "trace_available": True,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text("# summary\n", encoding="utf-8")

    result = execute_result(tool="runir.ps.base.execute_policy", result=Result(), output_dir=output_dir)

    assert result["items"] == [
        {
            "kind": "failure",
            "id": "open_state-001",
            "category": "open_state",
            "failure_category": "open_state",
            "problem_file": "p1.pddl",
            "task": "p1.pddl",
            "seed": 0,
            "path": witness_path.as_posix(),
            "trace_path": trace_path.as_posix(),
            "successors_path": successors_path.as_posix(),
            "meta_path": meta_path.as_posix(),
            "trace_available": True,
        }
    ]
    assert json.loads(witness_path.read_text(encoding="utf-8"))["id"] == "open_state-001"
    assert json.loads(trace_path.read_text(encoding="utf-8"))["id"] == "open_state-001"

def test_execute_result_exposes_successful_trace_artifacts(tmp_path):
    class Result:
        failure = None

    output_dir = tmp_path / "execute"
    success_dir = output_dir / "successes" / "success-001"
    trace_path = success_dir / "trace.psv"
    meta_path = success_dir / "meta.json"
    success_dir.mkdir(parents=True)
    trace_path.write_text("@id success-001\n", encoding="utf-8")
    meta_path.write_text(json.dumps({"id": "success-001", "category": "success"}) + "\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "tasks": [{"problem_file": "p1.pddl", "status": "SUCCESS", "seed": 0}],
                "distinct_failures": [],
                "successful_traces": [
                    {
                        "id": "success-001",
                        "category": "success",
                        "problem_file": "p1.pddl",
                        "seed": 0,
                        "trace_path": trace_path.as_posix(),
                        "meta_path": meta_path.as_posix(),
                        "trace_available": True,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = execute_result(tool="runir.ps.base.execute_policy", result=Result(), output_dir=output_dir)

    assert result["primary"]["successful"] is True
    assert result["primary"]["success_count"] == 1
    assert result["prompt_summary"]["counts"]["successes"] == 1
    assert result["items"] == []
    assert result["successes"] == [
        {
            "kind": "success",
            "id": "success-001",
            "category": "success",
            "problem_file": "p1.pddl",
            "task": "p1.pddl",
            "seed": 0,
            "trace_path": trace_path.as_posix(),
            "meta_path": meta_path.as_posix(),
            "trace_available": True,
        }
    ]


def test_base_execute_cli_passes_trace_metadata_options(monkeypatch, tmp_path):
    from pyrunir_mcp import invoke

    class Result:
        failure = None

    seen = {}

    def fake_execute(options):
        seen.update({
            "max_arity": options.max_arity,
            "num_rollouts": options.num_rollouts,
        })
        dump_dir = Path(options.dump_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / "manifest.json").write_text(
            '{"tasks": [], "distinct_failures": []}\n',
            encoding="utf-8",
        )
        return Result()

    monkeypatch.setattr(invoke, "execute_base_policy", fake_execute)
    result = invoke._base_execute(invoke.Args({
        "domain_file": str(tmp_path / "domain.pddl"),
        "problem_file": str(tmp_path / "problem.pddl"),
        "sketch_file": str(tmp_path / "sketch.txt"),
        "output_dir": str(tmp_path / "execute"),
        "max_arity": 1,
        "num_rollouts": 4,
    }))

    assert seen == {
        "max_arity": 1,
        "num_rollouts": 4,
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
