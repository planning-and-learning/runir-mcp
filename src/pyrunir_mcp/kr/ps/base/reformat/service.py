from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pyrunir_mcp.kr.ps.base.core.features import create_base_policy_context
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description

@dataclass(frozen=True)
class ReformatPolicyOptions:
    domain_path: Path
    policy_file: Path


@dataclass(frozen=True)
class CreateEmptyPolicyOptions:
    domain_path: Path
    policy_file: Path


@dataclass(frozen=True)
class ReformatPolicyResult:
    policy_file: Path
    kind: Literal["sketch"]


def reformat_policy(options: ReformatPolicyOptions) -> ReformatPolicyResult:
    context = create_base_policy_context(options.domain_path)
    description = options.policy_file.read_text(encoding="utf-8")
    parsed = parse_policy_description(context, description)
    options.policy_file.write_text(f"{parsed}\n", encoding="utf-8")
    return ReformatPolicyResult(policy_file=options.policy_file, kind="sketch")


def create_empty_policy(options: CreateEmptyPolicyOptions) -> ReformatPolicyResult:
    context = create_base_policy_context(options.domain_path)
    parsed = parse_policy_description(context, None)
    options.policy_file.parent.mkdir(parents=True, exist_ok=True)
    options.policy_file.write_text(f"{parsed}\n", encoding="utf-8")
    return ReformatPolicyResult(policy_file=options.policy_file, kind="sketch")
