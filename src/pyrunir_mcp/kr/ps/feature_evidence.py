from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias, runtime_checkable

from pyrunir.kr.ps.base.dl import (
    BooleanFeature as BaseBooleanFeature,
    NumericalFeature as BaseNumericalFeature,
)
from pyrunir.kr.ps.ext import (
    BooleanFeature as ExtBooleanFeature,
    ConceptFeature as ExtConceptFeature,
    NumericalFeature as ExtNumericalFeature,
)
from pytyr.planning.ground import State as GroundState

from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory
from pyrunir.kr.dl.base.semantics import GroundEvaluationContext as BaseGroundEvaluationContext
from pyrunir.kr.dl.ext.semantics import GroundEvaluationContext as ExtGroundEvaluationContext
from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HeuristicSentinel, HStarValue, LMCutValue

Feature: TypeAlias = (
    BaseBooleanFeature
    | BaseNumericalFeature
    | ExtConceptFeature
    | ExtBooleanFeature
    | ExtNumericalFeature
)
FeatureEvidence: TypeAlias = Callable[[GroundState], JsonObject]


@runtime_checkable
class NamedObject(Protocol):
    def get_name(self) -> str: ...


@runtime_checkable
class ObjectCollection(Protocol):
    def get_objects(self) -> list[NamedObject]: ...


class Stringable(Protocol):
    def __str__(self) -> str: ...


@runtime_checkable
class DenotationValue(Protocol):
    def get(self) -> SemanticValue: ...


SemanticValue: TypeAlias = JsonValue | ObjectCollection | DenotationValue | Stringable


def _object_name(value: NamedObject | Stringable) -> str:
    return str(value.get_name()) if isinstance(value, NamedObject) else str(value)


def json_value(value: SemanticValue) -> JsonValue:
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    if isinstance(value, ObjectCollection):
        return [_object_name(obj) for obj in value.get_objects()]
    if isinstance(value, DenotationValue) and type(value).__name__.endswith("Denotation"):
        return json_value(value.get())
    return str(value)


def feature_key(feature: Feature) -> str:
    variant = feature.get_variant()
    symbol = variant.get_symbol()
    return symbol or str(feature)


def _evaluate_feature_value(feature: Feature, state: GroundState) -> JsonValue:
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    if hasattr(feature, "evaluate"):
        context = BaseGroundEvaluationContext(state, builder, denotations)
        return json_value(feature.evaluate(context))
    context = ExtGroundEvaluationContext(state, builder, denotations)
    value = feature.get_variant().get_expression().evaluate(context)
    return json_value(value)


def evaluate_features(state: GroundState, features: list[Feature]) -> JsonObject:
    values: JsonObject = {}
    for feature in features:
        try:
            values[feature_key(feature)] = _evaluate_feature_value(feature, state)
        except RuntimeError as exc:
            values[feature_key(feature)] = {"error": str(exc)}
    return values


def state_facts(state: GroundState) -> JsonObject:
    return {
        "fluent_facts": [str(fact.get_atom()) for fact in state.fluent_facts()],
        "derived_atoms": [str(atom) for atom in state.derived_atoms()],
    }


def heuristic_json_value(value: HStarValue | LMCutValue) -> JsonValue:
    if isinstance(value, HeuristicSentinel):
        return value.value
    return value


def state_evidence(
    features: list[Feature],
    *,
    include_facts: bool,
    hstar: HStarEvaluator | None = None,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> FeatureEvidence:
    def evidence(state: GroundState) -> JsonObject:
        data: JsonObject = {"feature_values": evaluate_features(state, features)}
        if hstar is not None:
            if include_hstar:
                data["hstar"] = heuristic_json_value(hstar.evaluate(state))
            if include_hlmcut:
                data["hlmcut"] = heuristic_json_value(hstar.evaluate_lmcut(state))
        if include_facts:
            data.update(state_facts(state))
        return data

    return evidence
