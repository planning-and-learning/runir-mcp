from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from pyrunir_mcp.config import ServerConfig
from pyrunir_mcp.kr.ps.base import tools as base_tools
from pyrunir_mcp.kr.uns.reformat import tools as uns_reformat_tools
from pyrunir_mcp.kr.ps.ext.reformat import tools as ext_reformat_tools
from pyrunir_mcp.kr.ps.base.reformat import tools as base_reformat_tools
from pyrunir_mcp.paths import server_output_dir, server_output_path


class FakeMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, *, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


def test_server_output_dir_places_relative_paths_under_output_root(tmp_path):
    output_root = tmp_path / "mcp-output"

    assert server_output_dir(output_root, "prove/run") == output_root.resolve() / "prove" / "run"


def test_server_output_dir_accepts_absolute_paths_inside_output_root(tmp_path):
    output_root = tmp_path / "mcp-output"
    requested = output_root / "prove" / "run"

    assert server_output_dir(output_root, requested) == requested.resolve()


def test_server_output_dir_rejects_escape_paths(tmp_path):
    output_root = tmp_path / "mcp-output"

    with pytest.raises(ValueError):
        server_output_dir(output_root, "../outside")

    with pytest.raises(ValueError):
        server_output_dir(output_root, tmp_path / "outside")


def test_registered_base_tool_constrains_output_dir(monkeypatch, tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    captured = {}

    def fake_run(options):
        captured["output_dir"] = options.output_dir
        return {"status": "success"}

    monkeypatch.setattr(base_tools, "run_prove_policy", fake_run)
    base_tools.register_tools(mcp, config)

    result = mcp.tools[base_tools.TOOL_NAME](
        domain_file="domain.pddl",
        problem_file="problem.pddl",
        sketch_file="sketch.txt",
        output_dir="base/run",
    )

    assert result == {"status": "success"}
    assert captured["output_dir"] == (output_root / "base" / "run").resolve().as_posix()


def test_registered_base_tool_rejects_output_dir_escape(tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    base_tools.register_tools(mcp, config)

    with pytest.raises(ValueError):
        mcp.tools[base_tools.TOOL_NAME](
            domain_file="domain.pddl",
            problem_file="problem.pddl",
            sketch_file="sketch.txt",
            output_dir="../outside",
        )


def test_server_output_path_places_relative_paths_under_output_root(tmp_path):
    output_root = tmp_path / "mcp-output"

    assert server_output_path(output_root, "scratch/policy.txt") == (output_root / "scratch" / "policy.txt").resolve()


def test_server_output_path_rejects_escape_paths(tmp_path):
    output_root = tmp_path / "mcp-output"

    with pytest.raises(ValueError):
        server_output_path(output_root, "../policy.txt")

    with pytest.raises(ValueError):
        server_output_path(output_root, tmp_path / "outside" / "policy.txt")


def test_registered_base_reformat_constrains_sketch_file(monkeypatch, tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    captured = {}

    def fake_reformat(options):
        captured["sketch_file"] = options.sketch_file
        return SimpleNamespace(sketch_file=options.sketch_file, kind="sketch")

    monkeypatch.setattr(base_reformat_tools, "reformat_policy", fake_reformat)
    base_reformat_tools.register_tools(mcp, config)

    result = mcp.tools[base_reformat_tools.TOOL_NAME](
        domain_file="domain.pddl",
        sketch_file="scratch/sketch.txt",
    )

    expected = (output_root / "scratch" / "sketch.txt").resolve()
    assert Path(result["sketch_file"]) == expected
    assert captured["sketch_file"] == expected


def test_registered_ext_reformat_rejects_module_program_file_escape(tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    ext_reformat_tools.register_tools(mcp, config)

    with pytest.raises(ValueError):
        mcp.tools[ext_reformat_tools.MODULE_PROGRAM_TOOL_NAME](
            domain_file="domain.pddl",
            module_program_file="../module_program.txt",
        )


def test_registered_ext_reformat_rejects_module_file_escape(tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    ext_reformat_tools.register_tools(mcp, config)

    with pytest.raises(ValueError):
        mcp.tools[ext_reformat_tools.MODULE_TOOL_NAME](
            domain_file="domain.pddl",
            module_file="../module.txt",
        )


def test_registered_uns_reformat_constrains_classifier_file(monkeypatch, tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    captured = {}

    def fake_reformat(options):
        captured["classifier_file"] = options.classifier_file
        return SimpleNamespace(classifier_file=options.classifier_file, num_features=3)

    monkeypatch.setattr(uns_reformat_tools, "reformat_classifier", fake_reformat)
    uns_reformat_tools.register_tools(mcp, config)

    result = mcp.tools[uns_reformat_tools.TOOL_NAME](
        domain_file="domain.pddl",
        classifier_file="scratch/classifier.txt",
    )

    expected = (output_root / "scratch" / "classifier.txt").resolve()
    assert Path(result["classifier_file"]) == expected
    assert captured["classifier_file"] == expected


def test_registered_base_create_empty_constrains_sketch_file(monkeypatch, tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    captured = {}

    def fake_create(options):
        captured["sketch_file"] = options.sketch_file
        return SimpleNamespace(sketch_file=options.sketch_file, kind="sketch")

    monkeypatch.setattr(base_reformat_tools, "create_empty_policy", fake_create)
    base_reformat_tools.register_tools(mcp, config)

    result = mcp.tools[base_reformat_tools.CREATE_EMPTY_TOOL_NAME](
        domain_file="domain.pddl",
        sketch_file="scratch/sketch.txt",
    )

    expected = (output_root / "scratch" / "sketch.txt").resolve()
    assert Path(result["sketch_file"]) == expected
    assert captured["sketch_file"] == expected


def test_registered_ext_create_empty_constrains_module_program_file(monkeypatch, tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    captured = {}

    def fake_create(options):
        captured["module_program_file"] = options.module_program_file
        return SimpleNamespace(path=options.module_program_file, kind="module-program")

    monkeypatch.setattr(ext_reformat_tools, "create_empty_policy", fake_create)
    ext_reformat_tools.register_tools(mcp, config)

    result = mcp.tools[ext_reformat_tools.CREATE_EMPTY_TOOL_NAME](
        module_program_file="scratch/module_program.txt",
    )

    expected = (output_root / "scratch" / "module_program.txt").resolve()
    assert Path(result["module_program_file"]) == expected
    assert captured["module_program_file"] == expected


def test_registered_uns_create_empty_constrains_classifier_file(monkeypatch, tmp_path):
    output_root = tmp_path / "mcp-output"
    config = ServerConfig(workspace_root=tmp_path, output_root=output_root)
    mcp = FakeMCP()
    captured = {}

    def fake_create(options):
        captured["classifier_file"] = options.classifier_file
        return SimpleNamespace(classifier_file=options.classifier_file, num_features=0)

    monkeypatch.setattr(uns_reformat_tools, "create_empty_classifier", fake_create)
    uns_reformat_tools.register_tools(mcp, config)

    result = mcp.tools[uns_reformat_tools.CREATE_EMPTY_TOOL_NAME](classifier_file="scratch/classifier.txt")

    expected = (output_root / "scratch" / "classifier.txt").resolve()
    assert Path(result["classifier_file"]) == expected
    assert captured["classifier_file"] == expected
