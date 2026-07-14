from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from pyrunir_mcp import dumping
from pyrunir_mcp.dumping import SolutionResult
from pyrunir_mcp.enums import CounterexampleKind


def _proof(
    *,
    cycle: list[int] | None = None,
    deadend_states: list[int] | None = None,
    open_states: list[int] | None = None,
) -> object:
    return SimpleNamespace(
        graph=None,
        cycle=cycle or [],
        deadend_states=deadend_states or [],
        open_states=open_states or [],
    )


def test_universal_failure_evidence_has_one_extra_cycle_and_one_global_cap() -> None:
    result = SimpleNamespace(
        universal=True,
        num_rollouts=3,
        results=(
            (17, _proof(cycle=[7, 8], open_states=[1, 2])),
            (18, _proof(cycle=[9, 10], open_states=[3, 4])),
        ),
    )

    selected, regular_count = dumping.select_failure_evidence(
        cast(SolutionResult, result)
    )

    assert regular_count == 3
    assert [(item.seed, item.kind, item.witness) for item in selected] == [
        (None, CounterexampleKind.CYCLE, [7, 8]),
        (None, CounterexampleKind.OPEN_STATE, 1),
        (None, CounterexampleKind.OPEN_STATE, 2),
        (None, CounterexampleKind.OPEN_STATE, 3),
    ]


def test_existential_failure_evidence_keeps_rollout_seeds() -> None:
    result = SimpleNamespace(
        universal=False,
        num_rollouts=2,
        results=((4, _proof(open_states=[1])), (5, _proof(open_states=[2]))),
    )

    selected, regular_count = dumping.select_failure_evidence(
        cast(SolutionResult, result)
    )

    assert regular_count == 2
    assert [(item.seed, item.witness) for item in selected] == [(4, 1), (5, 2)]
