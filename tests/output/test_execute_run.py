from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.execute import Task, run_execute
from pyrunir_mcp.kr.ps.proof import ProofResult
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.tables import Document, Table


@dataclass(frozen=True)
class _Status:
    name: str
    value: str


@dataclass(frozen=True)
class _Result:
    status: _Status
    graph: object = None
    cycle: tuple[int, ...] = ()
    open_states: tuple[int, ...] = ()
    deadend_transitions: tuple[int, ...] = ()


@dataclass(frozen=True)
class _Task:
    problem_path: Path

    @property
    def search_context(self) -> object:
        return object()


def test_run_execute_keeps_seed_level_failures_and_successes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = _Task(tmp_path / "p01.pddl")
    results = {
        0: _Result(_Status("OUT_OF_STATES", "OUT_OF_STATES")),
        1: _Result(_Status("OUT_OF_STATES", "OUT_OF_STATES")),
        2: _Result(_Status("OUT_OF_STATES", "OUT_OF_STATES")),
        3: _Result(_Status("SUCCESS", "SUCCESS")),
        4: _Result(_Status("SUCCESS", "SUCCESS")),
    }

    def fake_successful_trace_artifact(*_args: object, **_kwargs: object) -> Document:
        return Document(header=[], sections=[Table("states", ["id"], [["s0"]])])

    monkeypatch.setattr(
        "pyrunir_mcp.kr.ps.execute.successful_trace_artifact",
        fake_successful_trace_artifact,
    )

    def solve(_task: object, seed: int) -> ProofResult:
        return cast(ProofResult, results[seed])

    run_execute(
        tool="base_execute",
        ext=False,
        output_dir=tmp_path,
        seeds=[0, 1, 2, 3, 4],
        tasks=[cast(Task, task)],
        solve=solve,
        feature_symbols=[],
        evidence=lambda _state: cast(JsonObject, {}),
        dicts=Dictionaries(),
        manifest_metadata={},
        formats=("psv",),
    )

    assert (tmp_path / "failures.psv").read_text(encoding="utf-8") == (
        "id|category|status|seed|problem|source|trace|witness|successors|plan_trace\n"
        "resource_limit-001|resource_limit|OUT_OF_STATES|0|p01.pddl|find_solution||||\n"
        "resource_limit-002|resource_limit|OUT_OF_STATES|1|p01.pddl|find_solution||||\n"
        "resource_limit-003|resource_limit|OUT_OF_STATES|2|p01.pddl|find_solution||||\n"
    )
    assert (tmp_path / "successes.psv").read_text(encoding="utf-8") == (
        "id|category|status|seed|problem|source|trace\n"
        "success-001|success|SUCCESS|3|p01.pddl|find_solution|successes/success-001/trace.psv\n"
        "success-002|success|SUCCESS|4|p01.pddl|find_solution|successes/success-002/trace.psv\n"
    )
