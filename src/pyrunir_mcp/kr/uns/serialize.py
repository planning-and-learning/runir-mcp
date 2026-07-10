from __future__ import annotations

from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
from pyrunir.kr.uns import Classifier


def feature_symbols(classifier: Classifier) -> list[str]:
    # The classifier `Feature` is a thin handle; the symbol and expression live on its
    # variant view (`get_variant()`), not on the handle itself.
    return [str(feature.get_variant().get_symbol()) for feature in classifier.get_features()]


def feature_values(classifier: Classifier, context: GroundEvaluationContext) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for feature in classifier.get_features():
        variant = feature.get_variant()
        values[str(variant.get_symbol())] = bool(variant.get_feature().evaluate(context))
    return values
