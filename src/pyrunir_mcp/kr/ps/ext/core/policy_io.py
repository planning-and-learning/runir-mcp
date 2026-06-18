from __future__ import annotations

from pathlib import Path

from pyrunir.kr.ps.ext import ModuleProgram, parse_module_program

from pyrunir_mcp.kr.ps.ext.core.features import FranceDLFeatureGenerator


def read_module_program_description(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_module_program_description(feature_generator: FranceDLFeatureGenerator, description: str) -> ModuleProgram:
    description = description.lstrip()
    if not description.startswith("(:program"):
        raise ValueError("Expected a full extended module program description starting with '(:program ...)'")
    return parse_module_program(description, feature_generator.planning_domain, feature_generator.policy_repository)
