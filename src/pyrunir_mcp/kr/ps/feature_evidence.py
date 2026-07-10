from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from pyrunir.kr.dl.base.semantics import (
    BooleanDenotation,
    Builder,
    ConceptDenotation,
    DenotationRepositoryFactory,
    NumericalDenotation,
    RoleDenotation,
)
from pyrunir.kr.dl.base.semantics import (
    GroundEvaluationContext as BaseGroundEvaluationContext,
)
from pyrunir.kr.dl.ext.semantics import GroundEvaluationContext as ExtGroundEvaluationContext
from pyrunir.kr.ps.base.dl import (
    BooleanFeature as BaseBooleanFeature,
)
from pyrunir.kr.ps.base.dl import (
    NumericalFeature as BaseNumericalFeature,
)
from pyrunir.kr.ps.ext.dl import (
    BooleanFeature as ExtBooleanFeature,
)
from pyrunir.kr.ps.ext.dl import (
    ConceptFeature as ExtConceptFeature,
)
from pyrunir.kr.ps.ext.dl import (
    NumericalFeature as ExtNumericalFeature,
)
from pytyr.planning.ground import State as GroundState

from pyrunir_mcp.enums import AtomKind, HeuristicSentinel
from pyrunir_mcp.json_types import JsonObject, JsonValue, normalize_json_value
from pyrunir_mcp.keys import (
    Keys,
)
from pyrunir_mcp.kr.ps.hstar import HStarEvaluator, HStarValue, LMCutValue

Feature: TypeAlias = (
    BaseBooleanFeature
    | BaseNumericalFeature
    | ExtConceptFeature
    | ExtBooleanFeature
    | ExtNumericalFeature
)
FeatureEvidence: TypeAlias = Callable[[GroundState], JsonObject]
AtomEvidence: TypeAlias = tuple[str, str]


SemanticValue: TypeAlias = (
    bool
    | int
    | float
    | str
    | None
    | BooleanDenotation
    | NumericalDenotation
    | ConceptDenotation
    | RoleDenotation
)


def json_value(value: SemanticValue) -> JsonValue:
    if isinstance(value, bool | int | float | str) or value is None:
        return normalize_json_value(value)
    if isinstance(value, BooleanDenotation | NumericalDenotation):
        return normalize_json_value(value.get())
    return str(value)


def feature_key(feature: Feature) -> str:
    variant = feature.get_variant()
    symbol = variant.get_symbol()
    return symbol or str(feature)


def _evaluate_feature_value(feature: Feature, state: GroundState) -> JsonValue:
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    if isinstance(feature, BaseBooleanFeature | BaseNumericalFeature):
        context = BaseGroundEvaluationContext(state, builder, denotations)
        return json_value(feature.evaluate(context))
    context = ExtGroundEvaluationContext(state, builder, denotations)
    return json_value(feature.get_variant().get_expression().evaluate(context))


def evaluate_features(state: GroundState, features: list[Feature]) -> JsonObject:
    values: JsonObject = {}
    for feature in features:
        try:
            values[feature_key(feature)] = _evaluate_feature_value(feature, state)
        except RuntimeError as exc:
            values[feature_key(feature)] = {Keys.ERROR: str(exc)}
    return values


def state_atom_evidence(state: GroundState) -> dict[AtomKind, tuple[str, ...]]:
    return {
        AtomKind.FLUENT: tuple(sorted(str(fact.get_atom()) for fact in state.fluent_facts())),
        AtomKind.DERIVED: tuple(sorted(str(atom) for atom in state.derived_atoms())),
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
        data: JsonObject = {Keys.FEATURE_VALUES: evaluate_features(state, features)}
        if hstar is not None:
            if include_hstar:
                data[Keys.HSTAR] = heuristic_json_value(hstar.evaluate(state))
            if include_hlmcut:
                data[Keys.HLMCUT] = heuristic_json_value(hstar.evaluate_lmcut(state))
        if include_facts:
            atoms = state_atom_evidence(state)
            data[Keys.FLUENT_ATOMS] = [atom for atom in atoms[AtomKind.FLUENT]]
            data[Keys.DERIVED_ATOMS] = [atom for atom in atoms[AtomKind.DERIVED]]
        return data

    return evidence
