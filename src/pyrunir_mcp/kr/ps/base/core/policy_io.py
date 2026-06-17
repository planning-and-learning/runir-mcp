from __future__ import annotations

import sys
from pathlib import Path

from pyrunir.kr.ps.base import Sketch as Policy
from pyrunir.kr.ps.base.dl import SketchFactory as PolicyFactory, parse_sketch as parse_policy

from pyrunir_mcp.kr.ps.base.core.features import FranceDLFeatureGenerator


def read_policy_description(path: Path | None) -> str | None:
    if path is None:
        return None
    if str(path) == "-":
        return sys.stdin.read()
    return path.read_text()


def create_empty_policy(feature_generator: FranceDLFeatureGenerator) -> Policy:
    return PolicyFactory.create_empty(feature_generator.policy_repository)


def parse_policy_description(feature_generator: FranceDLFeatureGenerator, description: str | None) -> Policy:
    if description is None:
        return create_empty_policy(feature_generator)
    description = description.lstrip()
    return parse_policy(description, feature_generator.planning_domain, feature_generator.policy_repository)
