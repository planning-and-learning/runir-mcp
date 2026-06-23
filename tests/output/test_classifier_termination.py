from pyrunir_mcp.output.classifier import ClassifierRow, counterexamples_table
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.termination import (
    TerminationDictionaries,
    TerminationEdge,
    TerminationVertex,
    counterexample_document,
)
from pyrunir_mcp.tables import render, render_document


def test_classifier_merged_table():
    dicts = Dictionaries()
    rows = [
        ClassifierRow("false_negative-001", "false_negative", 57, {"b_holding_target": True, "b_at_goal": False}, fluent=("at(robot roomA)", "holding(ball1)")),
        ClassifierRow("false_positive-001", "false_positive", 12, {"b_holding_target": False, "b_at_goal": True}, fluent=()),
    ]
    table = counterexamples_table(rows, ["b_holding_target", "b_at_goal"], dicts)
    assert render(table, "psv") == (
        "id|category|state|f0|f1|atoms\n"
        "false_negative-001|false_negative|57|T|F|p0,p1\n"
        "false_positive-001|false_positive|12|F|T|"
    )


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
