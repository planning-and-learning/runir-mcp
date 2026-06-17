from __future__ import annotations

from typing import Any

from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory, GroundEvaluationContext


def json_value(value: object) -> object:
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    return str(value)


def feature_key(feature: object) -> str:
    try:
        variant = feature.get_variant()
        symbol = variant.get_symbol()
        return symbol or str(feature)
    except Exception:  # noqa: BLE001
        return str(feature)


def evaluate_features(state: object, features: list[object]) -> dict[str, Any]:
    context = GroundEvaluationContext(state, Builder(), DenotationRepositoryFactory().create())
    values: dict[str, Any] = {}
    for feature in features:
        try:
            values[feature_key(feature)] = json_value(feature.evaluate(context))
        except Exception as exc:  # noqa: BLE001
            values[feature_key(feature)] = {"error": str(exc)}
    return values


def state_facts(state: object) -> dict[str, Any]:
    data: dict[str, Any] = {}
    try:
        data["static_atoms"] = [str(atom) for atom in state.static_atoms()]
        data["fluent_facts"] = [str(fact) for fact in state.fluent_facts()]
        data["derived_atoms"] = [str(atom) for atom in state.derived_atoms()]
    except Exception:  # noqa: BLE001
        pass
    return data


def state_evidence(features: list[object], *, include_facts: bool) -> object:
    def evidence(state: object) -> dict[str, Any]:
        data: dict[str, Any] = {"feature_values": evaluate_features(state, features)}
        if include_facts:
            data.update(state_facts(state))
        return data

    return evidence
