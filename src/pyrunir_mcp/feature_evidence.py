from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from pyrunir.kr.ps.base.dl import BooleanFeature as BaseBooleanFeature, NumericalFeature as BaseNumericalFeature
from pyrunir.kr.ps.ext import (
    BooleanFeature as ExtBooleanFeature,
    ConceptFeature as ExtConceptFeature,
    NumericalFeature as ExtNumericalFeature,
)
from pytyr.planning.ground import State

from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory, GroundEvaluationContext
from pyrunir_mcp.json_types import JsonObject, JsonValue

Feature: TypeAlias = (
    BaseBooleanFeature
    | BaseNumericalFeature
    | ExtConceptFeature
    | ExtBooleanFeature
    | ExtNumericalFeature
)
FeatureEvidence: TypeAlias = Callable[[State], JsonObject]



def _object_name(value) -> str:
    get_name = getattr(value, "get_name", None)
    if callable(get_name):
        return str(get_name())
    return str(value)


def json_value(value) -> JsonValue:
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    get_objects = getattr(value, "get_objects", None)
    if callable(get_objects):
        return [_object_name(obj) for obj in get_objects()]
    return str(value)


def feature_key(feature: Feature) -> str:
    try:
        variant = feature.get_variant()
        symbol = variant.get_symbol()
        return symbol or str(feature)
    except Exception:  # noqa: BLE001
        return str(feature)


def evaluate_features(state: State, features: list[Feature]) -> JsonObject:
    context = GroundEvaluationContext(state, Builder(), DenotationRepositoryFactory().create())
    values: JsonObject = {}
    for feature in features:
        try:
            values[feature_key(feature)] = json_value(feature.evaluate(context))
        except Exception as exc:  # noqa: BLE001
            values[feature_key(feature)] = {"error": str(exc)}
    return values


def state_facts(state: State) -> JsonObject:
    data: JsonObject = {}
    try:
        data["fluent_facts"] = [str(fact) for fact in state.fluent_facts()]
        data["derived_atoms"] = [str(atom) for atom in state.derived_atoms()]
    except Exception:  # noqa: BLE001
        pass
    return data


def state_evidence(features: list[Feature], *, include_facts: bool) -> FeatureEvidence:
    def evidence(state: State) -> JsonObject:
        data: JsonObject = {"feature_values": evaluate_features(state, features)}
        if include_facts:
            data.update(state_facts(state))
        return data

    return evidence
