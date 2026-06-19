from __future__ import annotations

from pyrunir_mcp.feature_evidence import json_value


class ObjectView:
    def __init__(self, name: str):
        self._name = name

    def get_name(self) -> str:
        return self._name


class ConceptDenotation:
    def get_objects(self) -> list[ObjectView]:
        return [ObjectView("loc1"), ObjectView("truck")]


def test_json_value_serializes_concept_denotations_as_object_names():
    assert json_value(ConceptDenotation()) == ["loc1", "truck"]
