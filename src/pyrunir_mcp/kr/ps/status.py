"""Shared success-status vocabulary for the policy tools.

Proof statuses (`SketchProofStatus`/`ModuleProgramProofStatus`) and greedy-execution search
statuses (`SearchStatus`) are distinct enums, but both spell a successful run as one of these
names. Comparing by name keeps a single source of truth across prove + execute.
"""

from __future__ import annotations

from typing import TypeAlias

from pyrunir.kr.ps.base import SketchProofStatus
from pyrunir.kr.ps.ext import ModuleProgramProofStatus

from pyrunir_mcp.enums import SuccessStatus

AnyStatus: TypeAlias = SuccessStatus | SketchProofStatus | ModuleProgramProofStatus

_SUCCESS_NAMES = frozenset(SuccessStatus)


def is_success_status(status: object) -> bool:
    name = getattr(status, "name", "")
    return str(name).lower() in _SUCCESS_NAMES
