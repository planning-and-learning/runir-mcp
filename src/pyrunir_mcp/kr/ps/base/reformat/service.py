from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pyrunir_mcp.kr.ps.base.core.features import create_france_dl_feature_generator
from pyrunir_mcp.kr.ps.base.core.policy_io import parse_policy_description

PolicyKind = Literal["auto", "sketch"]


@dataclass(frozen=True)
class ReformatPolicyOptions:
    domain_path: Path
    policy_file: Path
    kind: PolicyKind = "auto"
    create_empty: bool = False


@dataclass(frozen=True)
class ReformatPolicyResult:
    policy_file: Path
    kind: Literal["sketch"]


def reformat_policy(options: ReformatPolicyOptions) -> ReformatPolicyResult:
    if options.kind not in ("auto", "sketch"):
        raise ValueError(f"Unsupported policy kind: {options.kind}")

    feature_generator = create_france_dl_feature_generator(options.domain_path)
    # `create_empty` ignores any input and writes the canonical 0-width policy straight
    # from the Runir factory (`parse_policy_description(fg, None)` -> create_empty_policy),
    # so callers never hard-code a `(:sketch (:features) (:rules))` literal.
    description = None if options.create_empty else options.policy_file.read_text(encoding="utf-8")
    parsed = parse_policy_description(feature_generator, description)
    options.policy_file.write_text(f"{parsed}\n", encoding="utf-8")
    return ReformatPolicyResult(policy_file=options.policy_file, kind="sketch")
