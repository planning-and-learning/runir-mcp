from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pyrunir.kr.ps.ext import parse_module, parse_module_program

from pyrunir_mcp.kr.ps.ext.core.features import create_module_program_context

PolicyKind = Literal["auto", "module-program", "module"]


@dataclass(frozen=True)
class ReformatPolicyOptions:
    domain_path: Path
    policy_file: Path
    kind: PolicyKind = "auto"


@dataclass(frozen=True)
class ReformatPolicyResult:
    policy_file: Path
    kind: Literal["module-program", "module"]


def _detect_kind(description: str) -> Literal["module-program", "module"]:
    stripped = description.lstrip()
    if stripped.startswith("(:program"):
        return "module-program"
    if stripped.startswith("(:module"):
        return "module"
    raise ValueError("Expected a Runir extended module program '(:program ...)' or module '(:module ...)'.")


def reformat_policy(options: ReformatPolicyOptions) -> ReformatPolicyResult:
    description = options.policy_file.read_text(encoding="utf-8")
    kind = _detect_kind(description) if options.kind == "auto" else options.kind
    context = create_module_program_context(options.domain_path)

    if kind == "module-program":
        parsed = parse_module_program(description, context.planning_domain, context.policy_repository)
    elif kind == "module":
        parsed = parse_module(description, context.planning_domain, context.policy_repository)
    else:
        raise ValueError(f"Unsupported policy kind: {kind}")

    options.policy_file.write_text(f"{parsed}\n", encoding="utf-8")
    return ReformatPolicyResult(policy_file=options.policy_file, kind=kind)
