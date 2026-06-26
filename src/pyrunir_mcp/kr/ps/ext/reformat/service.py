from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pyrunir.kr.ps.ext import parse_module, parse_module_program

from pyrunir_mcp.kr.ps.ext.core.features import create_module_program_context

@dataclass(frozen=True)
class ReformatModuleProgramOptions:
    domain_path: Path
    module_program_file: Path


@dataclass(frozen=True)
class ReformatModuleOptions:
    domain_path: Path
    module_file: Path


@dataclass(frozen=True)
class CreateEmptyPolicyOptions:
    module_program_file: Path


@dataclass(frozen=True)
class ReformatPolicyResult:
    path: Path
    kind: Literal["module-program", "module"]


EMPTY_MODULE_PROGRAM = """\
(:program
    (:entry empty)
    (:module
        (:symbol empty)
        (:arguments)
        (:registers)
        (:entry m0)
        (:memory m0)
        (:features)
        (:rules)
    )
)
"""


def reformat_module_program(options: ReformatModuleProgramOptions) -> ReformatPolicyResult:
    description = options.module_program_file.read_text(encoding="utf-8")
    context = create_module_program_context(options.domain_path)
    parsed = parse_module_program(description, context.planning_domain, context.policy_repository)
    options.module_program_file.write_text(f"{parsed}\n", encoding="utf-8")
    return ReformatPolicyResult(path=options.module_program_file, kind="module-program")


def reformat_module(options: ReformatModuleOptions) -> ReformatPolicyResult:
    description = options.module_file.read_text(encoding="utf-8")
    context = create_module_program_context(options.domain_path)
    parsed = parse_module(description, context.planning_domain, context.policy_repository)
    options.module_file.write_text(f"{parsed}\n", encoding="utf-8")
    return ReformatPolicyResult(path=options.module_file, kind="module")


def create_empty_policy(options: CreateEmptyPolicyOptions) -> ReformatPolicyResult:
    options.module_program_file.parent.mkdir(parents=True, exist_ok=True)
    options.module_program_file.write_text(EMPTY_MODULE_PROGRAM + "\n", encoding="utf-8")
    return ReformatPolicyResult(path=options.module_program_file, kind="module-program")
