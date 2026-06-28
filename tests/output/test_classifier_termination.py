import pytest

from pyrunir_mcp.kr.ps.ext.termination.serialize import feature_symbol, rule_symbol, string_keyed_dict
from pyrunir_mcp.output.classifier import ClassifierRow, classifier_witness
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.termination import (
    TerminationDictionaries,
    TerminationEdge,
    TerminationVertex,
    counterexample_document,
)
from pyrunir_mcp.tables import render_document


def test_classifier_witness_document():
    dicts = Dictionaries()
    row = ClassifierRow(
        "false_negative-001", "false_negative", 57,
        {"b_holding_target": True, "b_at_goal": False}, fluent=("at(robot roomA)", "holding(ball1)"),
    )
    doc = classifier_witness(
        row, ["b_holding_target", "b_at_goal"], dicts,
        header=[("tool", "prove_classifier"), ("id", "false_negative-001"), ("category", "false_negative")],
    )
    psv = render_document(doc, "psv")
    assert "[state]\nid|flags|f0|f1\ns57|WITNESS|T|F" in psv
    assert "[facts]\nstate|atoms\ns57|p0,p1" in psv


def test_termination_cycle_document():
    dicts = TerminationDictionaries()
    vertices = [
        TerminationVertex(0, "q_init", concepts={"c_undelivered": "{b1,b2}"}, booleans={"b_holding": "T"}, numericals={"n_count": "3"}),
        TerminationVertex(1, "q_init", concepts={"c_undelivered": "{b1}"}, booleans={"b_holding": "T"}, numericals={"n_count": "2"}),
    ]
    edges = [
        TerminationEdge(0, 0, 1, "pickup", numerical_changes={"n_count": "dec"}),
        TerminationEdge(1, 1, 0, "advance", numerical_changes={"n_count": "inc"}),
    ]
    doc = counterexample_document(header=[("tool", "prove_termination")], vertices=vertices, edges=edges, dicts=dicts)
    psv = render_document(doc, "psv")
    assert "[cycle]\nkey|value\ncycle_vertex_indices|0,1,0\ncycle_edge_indices|0,1" in psv
    assert "[vertices]\nidx|mem|v0|v1|v2\n0|m0|{b1,b2}|T|3\n1|m0|{b1}|T|2" in psv
    assert "[edges]\nidx|src|tgt|rule|changes\n0|0|1|r0|v2:dec\n1|1|0|r1|v2:inc" in psv
    # variables interned concept, boolean, numerical in that grouping order
    assert dicts.tables()["variables"].rows == [["v0", "concept", "c_undelivered"], ["v1", "boolean", "b_holding"], ["v2", "numerical", "n_count"]]


class _Symbolic:
    def __init__(self, symbol: str):
        self._symbol = symbol

    def get_symbol(self) -> str:
        return self._symbol


class _FeatureLike:
    def __init__(self, symbol: str):
        self._variant = _Symbolic(symbol)

    def get_variant(self) -> _Symbolic:
        return self._variant


def test_termination_serializer_uses_feature_symbol_objects():
    assert string_keyed_dict({_FeatureLike("pending"): True}) == {"pending": "True"}


def test_termination_serializer_uses_rule_symbol_objects():
    assert rule_symbol(_Symbolic("put_down_pending")) == "put_down_pending"


def test_termination_serializer_requires_rule_symbol_accessor():
    with pytest.raises(AttributeError):
        rule_symbol("(:rule (:symbol put_down_pending))")


def test_termination_serializer_requires_feature_variant_symbol_accessor():
    with pytest.raises(AttributeError):
        feature_symbol(_Symbolic("pending"))
