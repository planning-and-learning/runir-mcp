"""Shared module-program introspection for the ext prove and execute services.

Both walk a `ModuleProgram` the same way to enumerate its memory-transition rules (for the
run-global `rules`/`memory` dictionaries) and to collect its declared features (deduped by
symbol). Keeping it here avoids the two services drifting apart.
"""

from __future__ import annotations

from typing import TypeAlias, cast

from pyrunir.kr.ps.ext import CallRule, DoRule, LoadRule, Module, ModuleProgram, SketchRule

from pyrunir_mcp.kr.ps.feature_evidence import Feature, feature_key
from pyrunir_mcp.output.dictionaries import Dictionaries

ModuleRule: TypeAlias = LoadRule | SketchRule | DoRule | CallRule


def iter_module_rules(program: ModuleProgram) -> list[tuple[Module, ModuleRule]]:
    rules: list[tuple[Module, ModuleRule]] = []
    for module in program.get_modules():
        for transition in module.get_memory_transitions():
            for rule_variant in transition:
                rules.append((module, cast(ModuleRule, rule_variant.get_variant())))
    return rules


def _declared_features(value: ModuleProgram | Module) -> list[Feature]:
    features: list[Feature] = []
    features.extend(cast(list[Feature], value.get_concept_features()))
    features.extend(cast(list[Feature], value.get_boolean_features()))
    features.extend(cast(list[Feature], value.get_numerical_features()))
    return features


def collect_features(program: ModuleProgram) -> list[Feature]:
    features_by_key: dict[str, Feature] = {}
    for value in (program, *program.get_modules()):
        for feature in _declared_features(value):
            features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def intern_rules(program: ModuleProgram, dicts: Dictionaries) -> None:
    """Populate the run-global rules dictionary (symbol -> src/tgt memory) up front, in policy
    order, so transition rows can resolve `rK` and ext rules carry their memory transition."""
    for module, rule in iter_module_rules(program):
        symbol = str(rule.get_symbol()).strip()
        if not symbol:
            continue
        module_name = str(module.get_name())
        source = dicts.memory(module_name, str(rule.get_source().get_name()), "")
        target = dicts.memory(module_name, str(rule.get_target().get_name()), "")
        dicts.rule(symbol, source, target)
