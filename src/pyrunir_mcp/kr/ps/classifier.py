from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pyrunir.kr import GroundTaskContext
from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
from pyrunir.kr.uns import Classifier, classify
from pyrunir.kr.uns import Repository as ClassifierRepository
from pyrunir.kr.uns.dl import ClassifierFactory, parse_classifier
from pytyr.formalism.planning import PlanningDomain
from pytyr.planning.ground import State

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.keys import (
    Keys,
)

StateEvidence = Callable[[State], JsonObject]


@dataclass(frozen=True)
class ClassifierContext:
    planning_domain: PlanningDomain
    classifier_repository: ClassifierRepository


def build_classifier(context: ClassifierContext, classifier_file: Path | None) -> Classifier:
    if classifier_file is None:
        return ClassifierFactory.create_empty(context.classifier_repository)
    return parse_classifier(
        Path(classifier_file).read_text(encoding="utf-8"),
        context.planning_domain,
        context.classifier_repository,
    )


def unsolvability_test(
    task_context: GroundTaskContext, classifier: Classifier
) -> Callable[[State], bool]:
    """Build a classifier predicate backed by the task's denotation cache."""
    builder = task_context.dl_builder
    denotations = task_context.dl_denotation_repository

    def is_unsolvable(state: State) -> bool:
        return bool(classify(classifier, GroundEvaluationContext(state, builder, denotations)))

    return is_unsolvable


def classifier_evidence(
    task_context: GroundTaskContext,
    evidence: StateEvidence,
    classifier: Classifier | None,
) -> StateEvidence:
    if classifier is None:
        return evidence

    is_unsolvable = unsolvability_test(task_context, classifier)

    def with_classifier(state: State) -> JsonObject:
        out = evidence(state)
        out[Keys.IS_UNSOLVABLE] = is_unsolvable(state)
        return out

    return with_classifier
