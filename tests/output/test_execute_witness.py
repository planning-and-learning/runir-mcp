from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.execute_witness import documents, successors
from pyrunir_mcp.tables import render_document

OPEN_TRACE = {
    "tool": "execute_policy",
    "id": "open_state-001",
    "failure_category": "open_state",
    "status": "OPEN",
    "problem_file": "p.pddl",
    "options": {"random_seed": 0},
    "features": ["n_undeliv"],
    "states": [
        {"state_index": 0, "feature_values": {"n_undeliv": 3}, "fluent_facts": ["at(a)"]},
        {"state_index": 5, "feature_values": {"n_undeliv": 2}, "fluent_facts": ["holding(b)"]},
    ],
    "transitions": [
        {"step": 0, "source_state_index": 0, "target_state_index": 5, "action": "(go)", "module_rule": "r1", "feature_delta": {"n_undeliv": {"before": 3, "after": 2}}},
    ],
}

CYCLE_TRACE = {
    "tool": "execute_policy",
    "id": "cycle-001",
    "failure_category": "cycle",
    "status": "CYCLE",
    "problem_file": "p.pddl",
    "options": {"random_seed": 0},
    "features": ["n_held"],
    "states": [
        {"state_index": 1, "feature_values": {"n_held": 1}},
        {"state_index": 2, "feature_values": {"n_held": 0}},
    ],
    "transitions": [
        {"step": 0, "source_state_index": 1, "target_state_index": 2, "action": "(drop)", "module_rule": "r_drop", "feature_delta": {"n_held": {"before": 1, "after": 0}}},
        {"step": 1, "source_state_index": 2, "target_state_index": 1, "action": "(pick)", "module_rule": "r_pick", "feature_delta": {"n_held": {"before": 0, "after": 1}}},
    ],
    "cycle": {"cycle_state_indices": [1, 2, 1], "cycle_transition_steps": [0, 1]},
}


def test_open_state_counterexample_and_trace():
    dicts = Dictionaries()
    counterexample, trace = documents(OPEN_TRACE, dicts, ext=False)
    cex_psv = render_document(counterexample, "psv")
    assert "[state]\nidx|flags|f0\n5|OPEN,WITNESS|2" in cex_psv
    assert "[facts]\nstate|atoms\n5|p1" in cex_psv  # at(a)=p0 interned first via the trace doc

    trace_psv = render_document(trace, "psv")
    assert "0|INIT|3" in trace_psv
    assert "5|OPEN,WITNESS|2" in trace_psv
    assert "[transitions]\nstep|src|tgt|rule|action|delta\n0|0|5|r0|a0|f0:3>2" in trace_psv


def test_cycle_counterexample_sections():
    dicts = Dictionaries()
    counterexample, _trace = documents(CYCLE_TRACE, dicts, ext=False)
    psv = render_document(counterexample, "psv")
    assert "[cycle]\nkey|value\ncycle_state_indices|1,2,1\ncycle_transition_steps|0,1" in psv
    assert "[states]\nidx|flags|f0\n1|INIT,CYCLE|1\n2|WITNESS,CYCLE|0" in psv
    assert "[transitions]\nstep|src|tgt|rule|action|delta\n0|1|2|r0|a0|f0:1>0\n1|2|1|r1|a1|f0:0>1" in psv


def test_successors_from_attached_rows():
    dicts = Dictionaries()
    trace = {
        **OPEN_TRACE,
        "successors": [
            {"src": 5, "action": "(deliver)", "module_rule": None, "feature_delta": {"n_undeliv": {"before": 2, "after": 1}}, "target": {"state_index": 9, "feature_values": {"n_undeliv": 1}, "is_goal": True}},
        ],
    }
    documents(trace, dicts, ext=False)  # intern features first (column order)
    doc = successors(trace, dicts, ext=False)
    psv = render_document(doc, "psv")
    assert "5|a1|9||GOAL|f0:2>1" in psv  # (go)=a0 interned first; empty rule = missing-guidance gap


def test_no_successors_returns_none():
    assert successors(OPEN_TRACE, Dictionaries(), ext=False) is None
