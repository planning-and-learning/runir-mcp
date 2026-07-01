from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.ps.hstar import HeuristicSentinel
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import counterexample_document, successors_document, trace_document
from pyrunir_mcp.output.proof_witness import successor, witness_state, witness_transition
from pyrunir_mcp.tables import render_document

BASE_STATE: JsonObject = {
    "vertex_index": 0,
    "state_index": 10,
    "feature_values": {"n_undeliv": 3, "b_goal": False},
    "fluent_facts": ["at(robot roomA)"],
    "derived_atoms": [],
    "is_initial": True,
    "is_goal": False,
    "is_unsolvable": False,
}
OPEN_STATE: JsonObject = {
    "vertex_index": 1,
    "state_index": 11,
    "feature_values": {"n_undeliv": 3, "b_goal": False},
    "fluent_facts": ["holding(ball1)"],
    "is_initial": False,
    "is_goal": False,
    "is_unsolvable": False,
}


def test_witness_state_flags_and_facts():
    state = witness_state(OPEN_STATE, witness=True, open_state=True)
    assert state.flags == ("OPEN", "WITNESS")
    assert state.state == 11
    assert state.fluent == ("holding(ball1)",)


def test_witness_state_deadend_and_initial_flags():
    assert witness_state(BASE_STATE).flags == ("INIT",)
    assert witness_state({**OPEN_STATE, "is_unsolvable": True}, witness=True).flags == ("WITNESS", "DEADEND")
    assert witness_state({**OPEN_STATE, "hstar": HeuristicSentinel.DEADEND}, witness=True).flags == ("WITNESS", "DEADEND")
    assert witness_state({**OPEN_STATE, "hlmcut": HeuristicSentinel.DEADEND}, witness=True).flags == ("WITNESS", "DEADEND")


def test_open_state_counterexample_document():
    dicts = Dictionaries()
    state = witness_state(OPEN_STATE, witness=True, open_state=True)
    doc = counterexample_document(
        header=[("tool", "prove_policy"), ("category", "open_state")],
        feature_symbols=["n_undeliv", "b_goal"],
        states=[state],
        transitions=[],
        cycle=None,
        dicts=dicts,
        ext=False,
    )
    psv = render_document(doc, "psv")
    assert "[state]\nid|flags|hstar|hlmcut|f0|f1\ns11|OPEN,WITNESS|||3|F" in psv
    assert "[facts]\nstate|atoms\ns11|p0" in psv


def test_trace_transitions_alias_and_delta():
    dicts = Dictionaries()
    dicts.rule("deliver")
    edge: JsonObject = {"action": "(deliver ball1)", "module_rule": "deliver"}
    transition = witness_transition(edge, step=0, source=BASE_STATE, target={**OPEN_STATE, "feature_values": {"n_undeliv": 2, "b_goal": False}}, ext=False)
    doc = trace_document(
        header=[("tool", "prove_policy")],
        feature_symbols=["n_undeliv", "b_goal"],
        states=[witness_state(BASE_STATE)],
        transitions=[transition],
        dicts=dicts,
        ext=False,
    )
    psv = render_document(doc, "psv")
    # base transition: src/tgt are state indices (10 -> 11), aliased rule/action, feature delta
    assert "0|s10|s11|r0|a0|f0:3>2" in psv


def test_ext_transition_uses_control_tuple_endpoints():
    src: JsonObject = {**BASE_STATE, "memory_state": "q0", "module": "m"}
    tgt: JsonObject = {**OPEN_STATE, "memory_state": "q1", "module": "m", "feature_values": {"n_undeliv": 2, "b_goal": False}}
    transition = witness_transition({"action": "(a)", "module_rule": "r"}, step=0, source=src, target=tgt, ext=True)
    assert transition.source == 10 and transition.target == 11
    assert transition.source_memory == ("m", "q0")
    assert transition.target_memory == ("m", "q1")


def test_successor_targets_and_gap():
    dicts = Dictionaries()
    src: JsonObject = BASE_STATE
    goal_target: JsonObject = {**OPEN_STATE, "state_index": 20, "is_goal": True, "feature_values": {"n_undeliv": 2, "b_goal": True}}
    succ = successor(src, {"action": "(deliver)", "module_rule": None}, goal_target)
    doc = successors_document(header=[("tool", "prove_policy")], feature_symbols=["n_undeliv", "b_goal"], successors=[succ], dicts=dicts, ext=False)
    psv = render_document(doc, "psv")
    # goal-reaching successor with an empty rule cell = the missing-guidance gap
    assert "s10|a0|s20||GOAL|f0:3>2 f1:F>T" in psv
    assert "[states]\nid|flags|hstar|hlmcut|f0|f1" in psv
