from __future__ import annotations



def fluent_facts(state: object) -> list[str]:
    try:
        return [str(fact) for fact in state.fluent_facts()]
    except Exception:  # noqa: BLE001
        return []


def feature_values(classifier: object, context: object) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for feature in classifier.get_features():
        symbol = getattr(feature, "get_symbol", lambda: str(feature))()
        try:
            expression = feature.get_variant()
        except Exception:  # noqa: BLE001
            try:
                expression = feature.get_feature()
            except Exception:  # noqa: BLE001
                continue
        try:
            values[str(symbol)] = bool(expression.evaluate(context))
        except Exception:  # noqa: BLE001
            values[str(symbol)] = False
    return values
