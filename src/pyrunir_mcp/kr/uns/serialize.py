from __future__ import annotations

from pyrunir.kr.uns import Classifier
from pytyr.planning.ground import State

try:
    from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
except ImportError:
    from pyrunir._pyrunir.kr.dl.uns.semantics import GroundEvaluationContext


def fluent_facts(state: State) -> list[str]:
    return [str(fact) for fact in state.fluent_facts()]


def _feature_expression(feature):
    get_variant = getattr(feature, "get_variant", None)
    if callable(get_variant):
        try:
            return get_variant()
        except AttributeError:
            pass
    get_feature = getattr(feature, "get_feature", None)
    if callable(get_feature):
        return get_feature()
    raise TypeError(f"{type(feature).__name__} does not expose get_variant() or get_feature()")


def feature_values(classifier: Classifier, context: GroundEvaluationContext) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for feature in classifier.get_features():
        symbol = getattr(feature, "get_symbol", lambda: str(feature))()
        expression = _feature_expression(feature)
        values[str(symbol)] = bool(expression.evaluate(context))
    return values
