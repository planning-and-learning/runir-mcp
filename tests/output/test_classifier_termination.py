from pyrunir_mcp.enums import RunItemCategory
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
        "false_negative-001",
        RunItemCategory.FALSE_NEGATIVE,
        57,
        {"b_holding_target": True, "b_at_goal": False},
        fluent=("at(robot roomA)", "holding(ball1)"),
        derived=("reachable(robot roomA)",),
    )
    doc = classifier_witness(
        row, ["b_holding_target", "b_at_goal"], dicts,
        header=[("tool", "prove_classifier"), ("id", "false_negative-001"), ("category", "false_negative")],
    )
    psv = render_document(doc, "psv")
    assert "[states]\nstate_id|flags|f0|f1\ns57|witness|T|F" in psv
    assert "[facts]\nstate_id|atom_ids\ns57|p0,p1,p2" in psv


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
    assert "[cycle]\nvertex_indices|edge_indices\n0,1,0|0,1" in psv
    assert "[vertices]\nvertex_index|memory_id|v0|v1|v2\n0|m0|{b1,b2}|T|3\n1|m0|{b1}|T|2" in psv
    assert "[edges]\nedge_index|source_vertex_index|target_vertex_index|rule_id|deltas\n0|0|1|r0|v2:dec\n1|1|0|r1|v2:inc" in psv
    # variables interned concept, boolean, numerical in that grouping order
    assert dicts.tables()["variables"].rows == [["v0", "concept", "c_undelivered"], ["v1", "boolean", "b_holding"], ["v2", "numerical", "n_count"]]


def test_base_termination_cycle_document_omits_memory():
    dicts = TerminationDictionaries()
    vertices = [
        TerminationVertex(
            0,
            None,
            booleans={"b_loaded": "T"},
            numericals={"n_remaining": ">0"},
        )
    ]
    edges = [
        TerminationEdge(
            0,
            0,
            0,
            "loop",
            numerical_changes={"n_remaining": "unchanged"},
        )
    ]
    doc = counterexample_document(
        header=[("tool", "runir.ps.base.prove_termination")],
        vertices=vertices,
        edges=edges,
        dicts=dicts,
        include_memory=False,
    )

    psv = render_document(doc, "psv")
    assert "[vertices]\nvertex_index|v0|v1\n0|T|>0" in psv
    assert "memory_id" not in psv
    assert set(dicts.tables(include_memory=False)) == {"variables", "rules"}
