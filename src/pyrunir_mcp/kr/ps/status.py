"""Shared success-status vocabulary for the policy tools.

Proof statuses (`SketchProofStatus`/`ModuleProgramProofStatus`) and greedy-execution search
statuses (`SearchStatus`) are distinct enums, but both spell a successful run as one of these
names. Comparing by name keeps a single source of truth across prove + execute.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class SuccessStatus(StrEnum):
    SOLVED = "SOLVED"
    SUCCESS = "SUCCESS"


_SUCCESS_NAMES = frozenset(SuccessStatus)


class NamedStatus(Protocol):
    name: str


def is_success_status(status: NamedStatus) -> bool:
    return status.name in _SUCCESS_NAMES
