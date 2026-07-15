from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast

from pyrunir.kr.ps.base import Sketch
from pyrunir.kr.ps.ext import ModuleProgram as ExtModuleProgram

from pyrunir_mcp.kr.ps.base.core.features import collect_features as collect_base_features
from pyrunir_mcp.kr.ps.ext.rules import collect_features as collect_ext_features


class Variant:
    def __init__(self, symbol: str):
        self._symbol = symbol

    def get_symbol(self) -> str:
        return self._symbol


class Feature:
    def __init__(self, symbol: str):
        self._variant = Variant(symbol)

    def get_variant(self) -> Variant:
        return self._variant


class SketchPolicy:
    def __init__(
        self,
        booleans: list[Feature] | None = None,
        numericals: list[Feature] | None = None,
    ):
        self._booleans = booleans or []
        self._numericals = numericals or []

    def get_boolean_features(self) -> list[Feature]:
        return self._booleans

    def get_numerical_features(self) -> list[Feature]:
        return self._numericals

    def get_rules(self):
        raise AssertionError("declared feature collection must not inspect rules")


class Module:
    def __init__(
        self,
        concepts: list[Feature] | None = None,
        roles: list[Feature] | None = None,
        booleans: list[Feature] | None = None,
        numericals: list[Feature] | None = None,
    ):
        self._concepts = concepts or []
        self._roles = roles or []
        self._booleans = booleans or []
        self._numericals = numericals or []

    def get_concept_features(self) -> list[Feature]:
        return self._concepts

    def get_role_features(self) -> list[Feature]:
        return self._roles

    def get_boolean_features(self) -> list[Feature]:
        return self._booleans

    def get_numerical_features(self) -> list[Feature]:
        return self._numericals


class ModuleProgram:
    def __init__(
        self,
        modules: list[Module],
        concepts: list[Feature] | None = None,
        booleans: list[Feature] | None = None,
        numericals: list[Feature] | None = None,
    ):
        self._modules = modules
        self._concepts = concepts or []
        self._booleans = booleans or []
        self._numericals = numericals or []

    def get_concept_features(self) -> list[Feature]:
        return self._concepts

    def get_boolean_features(self) -> list[Feature]:
        return self._booleans

    def get_numerical_features(self) -> list[Feature]:
        return self._numericals

    def get_modules(self) -> list[Module]:
        return self._modules

    def get_rules(self):
        raise AssertionError("declared feature collection must not inspect rules")


class SymbolicFeature(Protocol):
    def get_variant(self) -> Variant: ...


def _symbols(features: Sequence[SymbolicFeature]) -> list[str]:
    return [feature.get_variant().get_symbol() for feature in features]


def test_base_collectors_use_declared_sketch_features_only():
    policy = SketchPolicy(booleans=[Feature("a")], numericals=[Feature("a"), Feature("b")])

    features = cast(Sequence[SymbolicFeature], collect_base_features(cast(Sketch, policy)))
    assert _symbols(features) == ["a", "b"]


def test_ext_collectors_use_declared_module_features_only():
    program = ModuleProgram(
        [
            Module(
                concepts=[Feature("c")],
                roles=[Feature("r")],
                booleans=[Feature("b")],
            ),
            Module(
                concepts=[Feature("c")],
                roles=[Feature("r")],
                numericals=[Feature("n")],
            ),
        ]
    )

    features = cast(Sequence[SymbolicFeature], collect_ext_features(cast(ExtModuleProgram, program)))
    assert _symbols(features) == ["c", "r", "b", "n"]
