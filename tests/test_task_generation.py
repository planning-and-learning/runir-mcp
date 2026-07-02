from __future__ import annotations

import json
from pathlib import Path
from types import FunctionType
from typing import cast

import pytest

from pyrunir_mcp import DumpFormat, dump_result
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.task_generation import (
    GeneratedTask,
    InvalidTaskGenerationConfig,
    TaskGenerationOptions,
    TaskGenerationResult,
    batch_slug,
    fresh_problem_dir,
    task_generation,
    task_generation_json,
)


def _json_objects(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        raise TypeError("expected list of JSON objects")
    objects: list[JsonObject] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise TypeError("expected list of JSON objects")
        objects.append(cast(JsonObject, item))
    return objects


def test_public_api_exports_task_generation_names() -> None:
    import pyrunir_mcp as public

    assert public.GeneratedTask is GeneratedTask
    assert public.TaskGenerationResult is TaskGenerationResult
    assert callable(public.describe_generator)
    assert callable(public.generate_tasks)


def test_task_generation_dump_result_writes_summary_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "task_run"
    problem_dir = output_dir / "batch"
    problem_dir.mkdir(parents=True)
    domain = output_dir / "domain.pddl"
    generator = tmp_path / "generator.py"
    configs = problem_dir / "configs.json"
    pddl = problem_dir / "batch-001.pddl"
    domain.write_text("(define (domain d))", encoding="utf-8")
    generator.write_text("def make_problem(): pass", encoding="utf-8")
    configs.write_text("{}\n", encoding="utf-8")
    pddl.write_text("(define (problem p))", encoding="utf-8")

    result = TaskGenerationResult(
        domain_path=domain,
        problem_dir=problem_dir,
        generator_path=generator,
        signature="(n: int) -> str",
        generated=[GeneratedTask(index=1, path=pddl, config={"n": 1})],
        invalid=[InvalidTaskGenerationConfig(index=2, config={"n": 0}, reason="bad")],
    )
    dumped = dump_result(
        result, result.domain_path.parent, formats=(DumpFormat.JSON, DumpFormat.MD)
    )

    assert result.status == "failure"
    assert dumped.output_dir == output_dir
    assert dumped.files == (output_dir / "result.json", output_dir / "summary.md")
    assert (output_dir / "result.json").is_file()
    assert (output_dir / "summary.md").is_file()

    summary = cast(JsonObject, json.loads((output_dir / "result.json").read_text(encoding="utf-8")))
    generated = _json_objects(summary["generated"])
    invalid = _json_objects(summary["invalid"])
    assert summary["counts"] == {"generated": 1, "invalid": 1}
    assert generated[0]["path"] == pddl.as_posix()
    assert "absolute_path" not in generated[0]
    assert invalid[0]["reason"] == "bad"


def test_task_generation_dump_result_overwrites_result_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "task_run"
    problem_dir = output_dir / "batch"
    problem_dir.mkdir(parents=True)
    domain = output_dir / "domain.pddl"
    generator = tmp_path / "generator.py"
    pddl = problem_dir / "batch-001.pddl"
    domain.write_text("(define (domain d))", encoding="utf-8")
    generator.write_text("def make_problem(): pass", encoding="utf-8")
    pddl.write_text("(define (problem p))", encoding="utf-8")
    (output_dir / "result.json").write_text("stale\n", encoding="utf-8")

    result = TaskGenerationResult(
        domain_path=domain,
        problem_dir=problem_dir,
        generator_path=generator,
        signature="() -> str",
        generated=[GeneratedTask(index=1, path=pddl, config={})],
        invalid=[],
    )

    dumped = dump_result(result, result.domain_path.parent)

    assert dumped.files == (output_dir / "result.json",)
    assert (
        json.loads((output_dir / "result.json").read_text(encoding="utf-8"))["tool"]
        == "runir.task_generation"
    )


def test_reused_task_batch_allocates_child_batch(tmp_path: Path) -> None:
    output_dir = tmp_path / "task_run"
    first = output_dir / "batch"
    first.mkdir(parents=True)
    (first / "batch-001.pddl").write_text("old", encoding="utf-8")

    fresh = fresh_problem_dir(output_dir, "batch")

    assert fresh == output_dir / "batch-002"
    assert (first / "batch-001.pddl").read_text(encoding="utf-8") == "old"


def test_reused_numbered_task_batch_skips_occupied_child(tmp_path: Path) -> None:
    output_dir = tmp_path / "task_run"
    first = output_dir / "batch"
    second = output_dir / "batch-002"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "batch-001.pddl").write_text("old", encoding="utf-8")
    (second / "batch-001.pddl").write_text("also old", encoding="utf-8")

    fresh = fresh_problem_dir(output_dir, "batch")

    assert fresh == output_dir / "batch-003"
    assert (first / "batch-001.pddl").read_text(encoding="utf-8") == "old"
    assert (second / "batch-001.pddl").read_text(encoding="utf-8") == "also old"


def test_task_batch_name_is_slugged_inside_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "task_run"

    fresh = fresh_problem_dir(output_dir, "../bad/name")

    assert batch_slug("../bad/name") == "bad_name"
    assert fresh == output_dir / "bad_name"
    assert fresh.is_relative_to(output_dir)
    assert not (tmp_path / "bad").exists()


def test_existing_task_tree_forces_child_run(tmp_path: Path) -> None:
    from pyrunir_mcp.artifacts import fresh_output_dir

    output_dir = tmp_path / "task_run"
    stale_tree = output_dir / "dicts"
    stale_tree.mkdir(parents=True)
    (stale_tree / "old.json").write_text("{}\n", encoding="utf-8")

    fresh = fresh_output_dir(output_dir)

    assert fresh == output_dir / "run-002"
    assert (stale_tree / "old.json").is_file()
    assert (output_dir / "run-002" / ".pyrunir-mcp-output").is_file()


def test_fresh_output_dir_reserves_empty_directory(tmp_path: Path) -> None:
    from pyrunir_mcp.artifacts import fresh_output_dir

    output_dir = tmp_path / "task_run"
    output_dir.mkdir()

    first = fresh_output_dir(output_dir)
    second = fresh_output_dir(output_dir)

    assert first == output_dir
    assert second == output_dir / "run-002"
    assert (output_dir / ".pyrunir-mcp-output").is_file()
    assert (output_dir / "run-002" / ".pyrunir-mcp-output").is_file()


def test_reused_task_generation_output_allocates_child_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import pyrunir_mcp.task_generation as service_module

    output_dir = tmp_path / "task_run"
    source_domain = tmp_path / "source-domain.pddl"
    generator = tmp_path / "generator.py"
    source_domain.write_text("(define (domain d))", encoding="utf-8")
    generator.write_text("def make_problem(n): pass", encoding="utf-8")

    def fake_generator_path(domain_name: str) -> Path:
        return generator

    def fake_generator_domain_path(domain_name: str) -> Path:
        return source_domain

    def fake_make_problem(n: int) -> str:
        return f"(define (problem p{n}))"

    def fake_load_make_problem(domain_name: str) -> FunctionType:
        return fake_make_problem

    monkeypatch.setattr(service_module, "get_generator_path", fake_generator_path)
    monkeypatch.setattr(service_module, "get_generator_domain_path", fake_generator_domain_path)
    monkeypatch.setattr(service_module, "load_make_problem", fake_load_make_problem)

    opts = TaskGenerationOptions(
        domain_name="gripper",
        output_dir=output_dir,
        batch_name="batch",
        configs=[{"n": 1}],
    )
    first = task_generation(opts)
    first_dump = dump_result(first, first.domain_path.parent)
    second = task_generation(opts)
    second_dump = dump_result(second, second.domain_path.parent)

    assert first_dump.output_dir == output_dir
    assert second_dump.output_dir == output_dir / "run-002"
    assert (output_dir / "result.json").is_file()
    assert (output_dir / "run-002" / "result.json").is_file()
    assert first.problem_dir == output_dir / "batch"
    assert second.problem_dir == output_dir / "run-002" / "batch"


def test_task_generation_uses_slugged_batch_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import pyrunir_mcp.task_generation as service_module

    output_dir = tmp_path / "task_run"
    source_domain = tmp_path / "source-domain.pddl"
    generator = tmp_path / "generator.py"
    source_domain.write_text("(define (domain d))", encoding="utf-8")
    generator.write_text("def make_problem(n): pass", encoding="utf-8")

    def fake_generator_path(domain_name: str) -> Path:
        return generator

    def fake_generator_domain_path(domain_name: str) -> Path:
        return source_domain

    def fake_make_problem(n: int) -> str:
        return f"(define (problem p{n}))"

    def fake_load_make_problem(domain_name: str) -> FunctionType:
        return fake_make_problem

    monkeypatch.setattr(service_module, "get_generator_path", fake_generator_path)
    monkeypatch.setattr(service_module, "get_generator_domain_path", fake_generator_domain_path)
    monkeypatch.setattr(service_module, "load_make_problem", fake_load_make_problem)

    result = task_generation(
        TaskGenerationOptions(
            domain_name="gripper",
            output_dir=output_dir,
            batch_name="../bad/name",
            configs=[{"n": 1}],
        )
    )
    summary = task_generation_json(result)

    generated = _json_objects(summary["generated"])
    configs = cast(
        JsonObject,
        json.loads((output_dir / "bad_name" / "configs.json").read_text(encoding="utf-8")),
    )
    config_generated = _json_objects(configs["generated"])

    assert result.problem_dir == output_dir / "bad_name"
    assert result.generated[0].path == output_dir / "bad_name" / "bad_name-001.pddl"
    assert generated[0]["path"] == (output_dir / "bad_name" / "bad_name-001.pddl").as_posix()
    assert config_generated[0]["path"] == (output_dir / "bad_name" / "bad_name-001.pddl").as_posix()
    assert not (tmp_path / "bad").exists()
