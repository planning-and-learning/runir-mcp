from __future__ import annotations

from pyrunir_mcp.kr.ps.base.service import collect_features as collect_base_features
from pyrunir_mcp.kr.ps.ext.service import collect_features as collect_ext_features
from pyrunir_mcp.kr.ps.base.execute.service import _collect_features as collect_base_execute_features
from pyrunir_mcp.kr.ps.ext.execute.service import _collect_features as collect_ext_execute_features


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
        booleans: list[Feature] | None = None,
        numericals: list[Feature] | None = None,
    ):
        self._concepts = concepts or []
        self._booleans = booleans or []
        self._numericals = numericals or []

    def get_concept_features(self) -> list[Feature]:
        return self._concepts

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


def _symbols(features: list[Feature]) -> list[str]:
    return [feature.get_variant().get_symbol() for feature in features]


def test_base_collectors_use_declared_sketch_features_only():
    policy = SketchPolicy(booleans=[Feature("a")], numericals=[Feature("a"), Feature("b")])

    assert _symbols(collect_base_features(policy)) == ["a", "b"]
    assert _symbols(collect_base_execute_features(policy)) == ["a", "b"]


def test_ext_collectors_use_declared_module_features_only():
    program = ModuleProgram(
        [
            Module(concepts=[Feature("c")], booleans=[Feature("b")]),
            Module(concepts=[Feature("c")], numericals=[Feature("n")]),
        ]
    )

    assert _symbols(collect_ext_features(program)) == ["c", "b", "n"]
    assert _symbols(collect_ext_execute_features(program)) == ["c", "b", "n"]
