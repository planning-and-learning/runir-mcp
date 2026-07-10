from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from pyrunir.kr.ps.base import Sketch
from pyrunir.kr.ps.ext import ModuleProgram as RunirModuleProgram
from pyrunir.kr.uns import Classifier as RunirClassifier

from pyrunir_mcp.enums import CandidateSource


@dataclass(frozen=True, slots=True)
class Policy:
    id: str
    value: Sketch
    source: CandidateSource
    source_file: Path | None = None


@dataclass(frozen=True, slots=True)
class ModuleProgram:
    id: str
    value: RunirModuleProgram
    source: CandidateSource
    source_file: Path | None = None


@dataclass(frozen=True, slots=True)
class Classifier:
    id: str
    value: RunirClassifier
    source: CandidateSource
    source_file: Path | None = None


Candidate: TypeAlias = Policy | ModuleProgram | Classifier
