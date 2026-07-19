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
        TerminationVertex(
            0,
            "q_init",
            booleans={"b_holding": True},
            numericals={"n_count": True},
        ),
        TerminationVertex(
            1,
            "q_init",
            booleans={"b_holding": False},
            numericals={"n_count": False},
        ),
    ]
    edges = [
        TerminationEdge(
            0,
            0,
            1,
            "pickup",
            boolean_changes={"b_holding": "↓"},
            numerical_changes={"n_count": "↓"},
        ),
        TerminationEdge(
            1,
            1,
            0,
            "advance",
            boolean_changes={"b_holding": "↑"},
            numerical_changes={"n_count": "↑"},
        ),
    ]
    doc = counterexample_document(header=[("tool", "prove_termination")], vertices=vertices, edges=edges, dicts=dicts)
    psv = render_document(doc, "psv")
    assert "[cycle]" not in psv
    assert "[vertices]\nvertex_index|memory_id|valuation\n0|m0|v0 v1\n1|m0|¬v0 ¬v1" in psv
    assert "[edges]\nedge_index|source_vertex_index|target_vertex_index|rule_id|deltas\n0|0|1|r0|v0↓ v1↓\n1|1|0|r1|v0↑ v1↑" in psv
    assert dicts.tables()["variables"].rows == [
        ["v0", "boolean", "b_holding"],
        ["v1", "numerical", "n_count"],
    ]


def test_base_termination_cycle_document_omits_memory():
    dicts = TerminationDictionaries()
    vertices = [
        TerminationVertex(
            0,
            None,
            booleans={"b_loaded": True},
            numericals={"n_remaining": True},
        )
    ]
    edges = [
        TerminationEdge(
            0,
            0,
            0,
            "loop",
            boolean_changes={"b_loaded": "="},
            numerical_changes={"n_remaining": "="},
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
    assert "[vertices]\nvertex_index|valuation\n0|v0 v1" in psv
    assert "[edges]\nedge_index|source_vertex_index|target_vertex_index|rule_id|deltas\n0|0|0|r0|v0= v1=" in psv
    assert "memory_id" not in psv
    assert set(dicts.tables(include_memory=False)) == {"variables", "rules"}
