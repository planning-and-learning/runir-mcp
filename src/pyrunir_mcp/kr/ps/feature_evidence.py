from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias, runtime_checkable

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


@runtime_checkable
class NamedObject(Protocol):
    def get_name(self) -> str: ...


@runtime_checkable
class ObjectCollection(Protocol):
    def get_objects(self) -> list[NamedObject]: ...


def _object_name(value: NamedObject | object) -> str:
    return str(value.get_name()) if isinstance(value, NamedObject) else str(value)


def json_value(value) -> JsonValue:
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    if isinstance(value, ObjectCollection):
        return [_object_name(obj) for obj in value.get_objects()]
    return str(value)


def feature_key(feature: Feature) -> str:
    variant = feature.get_variant()
    symbol = variant.get_symbol()
    return symbol or str(feature)


def evaluate_features(state: State, features: list[Feature]) -> JsonObject:
    context = GroundEvaluationContext(state, Builder(), DenotationRepositoryFactory().create())
    values: JsonObject = {}
    for feature in features:
        try:
            values[feature_key(feature)] = json_value(feature.evaluate(context))
        except RuntimeError as exc:
            values[feature_key(feature)] = {"error": str(exc)}
    return values


def state_facts(state: State) -> JsonObject:
    return {
        "fluent_facts": [str(fact) for fact in state.fluent_facts()],
        "derived_atoms": [str(atom) for atom in state.derived_atoms()],
    }


def state_evidence(features: list[Feature], *, include_facts: bool) -> FeatureEvidence:
    def evidence(state: State) -> JsonObject:
        data: JsonObject = {"feature_values": evaluate_features(state, features)}
        if include_facts:
            data.update(state_facts(state))
        return data

    return evidence
