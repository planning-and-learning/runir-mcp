from __future__ import annotations

from pathlib import Path
from typing import Callable

from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory
from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
from pyrunir.kr.uns import Repository as ClassifierRepository, classify
from pyrunir.kr.uns.dl import ClassifierFactory, parse_classifier
from pytyr.formalism.planning import PlanningDomain
from pytyr.planning.ground import State

from pyrunir_mcp.json_types import JsonObject

Classifier = object
StateEvidence = Callable[[State], JsonObject]


def build_classifier(repository: ClassifierRepository, domain: PlanningDomain, classifier_file: Path | None) -> Classifier:
    if classifier_file is None:
        return ClassifierFactory.create_empty(repository)
    return parse_classifier(Path(classifier_file).read_text(encoding="utf-8"), domain, repository)


def classifier_evidence(evidence: StateEvidence, classifier: Classifier | None) -> StateEvidence:
    if classifier is None:
        return evidence

    builder = Builder()
    denotations = DenotationRepositoryFactory().create()

    def with_classifier(state: State) -> JsonObject:
        out = evidence(state)
        out["is_unsolvable"] = bool(classify(classifier, GroundEvaluationContext(state, builder, denotations)))
        return out

    return with_classifier
