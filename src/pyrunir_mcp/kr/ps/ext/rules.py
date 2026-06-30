"""Shared module-program introspection for the ext prove and execute services.

Both walk a `ModuleProgram` the same way to enumerate its memory-transition rules (for the
run-global `rules`/`memory` dictionaries) and to collect its declared features (deduped by
symbol). Keeping it here avoids the two services drifting apart.
"""

from __future__ import annotations

from typing import TypeAlias, cast

from pyrunir.kr.ps.ext import CallRule, ConceptLoadRule, DoRule, Module, ModuleProgram, RoleLoadRule, RuleVariant, SketchRule

from pyrunir_mcp.kr.ps.feature_evidence import Feature, feature_key
from pyrunir_mcp.output.dictionaries import Dictionaries

ModuleRule: TypeAlias = ConceptLoadRule | RoleLoadRule | SketchRule | DoRule | CallRule


def iter_module_rules(program: ModuleProgram) -> list[tuple[Module, RuleVariant, ModuleRule]]:
    rules: list[tuple[Module, RuleVariant, ModuleRule]] = []
    for module in program.get_modules():
        for transition in module.get_memory_transitions():
            for rule_variant in transition:
                rules.append((module, rule_variant, rule_variant.get_variant()))
    return rules


def _declared_features(module: Module) -> list[Feature]:
    features: list[Feature] = []
    # pyrunir returns family-specific feature lists; Feature is the shared MCP union over them.
    features.extend(cast(list[Feature], module.get_concept_features()))
    features.extend(cast(list[Feature], module.get_boolean_features()))
    features.extend(cast(list[Feature], module.get_numerical_features()))
    return features


def collect_features(program: ModuleProgram) -> list[Feature]:
    # Features are declared on the modules; the ModuleProgram is just the wiring of modules.
    features_by_key: dict[str, Feature] = {}
    for module in program.get_modules():
        for feature in _declared_features(module):
            features_by_key.setdefault(feature_key(feature), feature)
    return list(features_by_key.values())


def intern_rules(program: ModuleProgram, dicts: Dictionaries) -> None:
    """Populate the run-global rules dictionary (symbol -> src/tgt memory) up front, in policy
    order, so transition rows can resolve `rK` and ext rules carry their memory transition."""
    for module, rule_variant, rule in iter_module_rules(program):
        symbol = str(rule_variant.get_symbol()).strip()
        if not symbol:
            continue
        module_alias = dicts.module(str(module.get_name()))
        source = dicts.memory(module_alias, str(rule.get_source().get_name()))
        target = dicts.memory(module_alias, str(rule.get_target().get_name()))
        dicts.rule(symbol, source, target)
