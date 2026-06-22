from __future__ import annotations

from pyrunir.kr.uns import Classifier
from pytyr.planning.ground import State

from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext


def fluent_facts(state: State) -> list[str]:
    return [str(fact) for fact in state.fluent_facts()]


def feature_values(classifier: Classifier, context: GroundEvaluationContext) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for feature in classifier.get_features():
        symbol = str(feature.get_symbol())
        expression = feature.get_feature()
        values[symbol] = bool(expression.evaluate(context))
    return values
