from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import (
    Cycle,
    Successor,
    WitnessState,
    WitnessTransition,
    counterexample_document,
    resolve_flags,
    successors_document,
    trace_document,
)
from pyrunir_mcp.tables import render_document

HEADER = [("tool", "execute_policy"), ("id", "cycle-001"), ("category", "cycle"), ("status", "CYCLE"), ("problem", "p01.pddl")]
FEATURES = ["n_undeliv", "n_held", "b_atgoal"]


def test_resolve_flags():
    assert resolve_flags(initial=True) == ("INIT",)
    assert resolve_flags(deadend=True) == ("DEADEND",)
    assert resolve_flags(witness=True, cycle=True) == ("WITNESS", "CYCLE")
    assert resolve_flags() == ()


def test_trace_document_matches_doc():
    dicts = Dictionaries()
    dicts.rule("pickup_r1")
    dicts.rule("deliver_r2")
    states = [
        WitnessState(0, {"n_undeliv": 3, "n_held": 0, "b_atgoal": False}, fluent=("at(robot roomA)",), flags=("INIT",)),
        WitnessState(1, {"n_undeliv": 2, "n_held": 1, "b_atgoal": False}, fluent=("holding(ball1)",)),
        WitnessState(2, {"n_undeliv": 2, "n_held": 0, "b_atgoal": False}, flags=("CYCLE",)),
    ]
    transitions = [
        WitnessTransition(0, 0, 1, action="(pickup ball1 roomA)", rule="pickup_r1", delta={"n_held": (0, 1)}),
        WitnessTransition(1, 1, 2, action="(drop ball1 roomB)", rule="deliver_r2", delta={"n_undeliv": (3, 2), "n_held": (1, 0)}),
    ]
    doc = trace_document(header=HEADER, feature_symbols=FEATURES, states=states, transitions=transitions, dicts=dicts, ext=False)
    assert render_document(doc, "psv") == (
        "@tool execute_policy\n@id cycle-001\n@category cycle\n@status CYCLE\n@problem p01.pddl\n"
        "\n[states]\nid|flags|f0|f1|f2\ns0|INIT|3|0|F\ns1||2|1|F\ns2|CYCLE|2|0|F\n"
        "\n[transitions]\nstep|source|target|rule|action|delta\n0|s0|s1|r0|a0|f1:0>1\n1|s1|s2|r1|a1|f0:3>2 f1:1>0\n"
        "\n[facts]\nstate|atoms\ns0|p0\ns1|p1"
    )


def test_cycle_counterexample_matches_doc():
    dicts = Dictionaries()
    # Run-global dictionaries already populated by an earlier witness (alias order fixed).
    for symbol in FEATURES:
        dicts.feature(symbol)
    dicts.rule("pickup_r1")
    dicts.rule("deliver_r2")
    dicts.action("(pickup ball1 roomA)")
    dicts.action("(drop ball1 roomB)")
    dicts.atom("fluent", "at(robot roomA)")
    dicts.atom("fluent", "holding(ball1)")
    states = [
        WitnessState(1, {"n_undeliv": 2, "n_held": 1, "b_atgoal": False}, fluent=("holding(ball1)",), flags=("CYCLE",)),
        WitnessState(2, {"n_undeliv": 2, "n_held": 0, "b_atgoal": False}, fluent=("at(robot roomA)",), flags=("CYCLE",)),
    ]
    transitions = [
        WitnessTransition(0, 1, 2, action="(drop ball1 roomB)", rule="deliver_r2", delta={"n_held": (1, 0)}),
        WitnessTransition(1, 2, 1, action="(pickup ball1 roomA)", rule="pickup_r1", delta={"n_held": (0, 1)}),
    ]
    cycle = Cycle(state_indices=(1, 2, 1), transition_steps=(0, 1))
    doc = counterexample_document(header=HEADER, feature_symbols=FEATURES, states=states, transitions=transitions, cycle=cycle, dicts=dicts, ext=False)
    assert render_document(doc, "psv") == (
        "@tool execute_policy\n@id cycle-001\n@category cycle\n@status CYCLE\n@problem p01.pddl\n"
        "\n[cycle]\nkey|value\ncycle_state_indices|s1,s2,s1\ncycle_transition_steps|0,1\n"
        "\n[states]\nid|flags|f0|f1|f2\ns1|CYCLE|2|1|F\ns2|CYCLE|2|0|F\n"
        "\n[transitions]\nstep|source|target|rule|action|delta\n0|s1|s2|r1|a1|f1:1>0\n1|s2|s1|r0|a0|f1:0>1\n"
        "\n[facts]\nstate|atoms\ns1|p1\ns2|p0"
    )


def test_state_witness_uses_singular_state_section():
    dicts = Dictionaries()
    state = WitnessState(42, {"n_undeliv": 3}, fluent=("at(robot roomA)",), flags=("OPEN", "WITNESS"))
    doc = counterexample_document(header=[("id", "open-001")], feature_symbols=["n_undeliv"], states=[state], transitions=[], cycle=None, dicts=dicts, ext=False)
    psv = render_document(doc, "psv")
    assert "[state]\nid|flags|f0\ns42|OPEN,WITNESS|3" in psv
    assert "[states]" not in psv


def test_successors_document_shows_empty_rule_gap():
    dicts = Dictionaries()
    dicts.rule("deliver_r2")  # r0
    successors = [
        Successor(src=1, target=WitnessState(60, {"n_undeliv": 1}, flags=("GOAL",)), action="(deliver ball1)", rule=None, delta={"n_undeliv": (2, 1)}),
        Successor(src=2, target=WitnessState(61, {"n_undeliv": 3}, flags=("DEADEND",)), action="(drop ball1)", rule="deliver_r2", delta={"n_undeliv": (2, 3)}),
    ]
    doc = successors_document(header=[("id", "cycle-001")], feature_symbols=["n_undeliv"], successors=successors, dicts=dicts, ext=False)
    psv = render_document(doc, "psv")
    # goal-reaching escape with empty rule cell = the missing-guidance gap
    assert "s1|a0|s60||GOAL|f0:2>1" in psv
    assert "s2|a1|s61|r0|DEADEND|f0:2>3" in psv


def test_ext_state_columns_include_vtx_mod_and_mem():
    dicts = Dictionaries(ext=True)
    mem = ("deliver", "q_init")  # (module, memory)
    state = WitnessState(10, {"n_held": 1}, flags=("CYCLE",), vertex=3, memory=mem)
    doc = counterexample_document(header=[("id", "c")], feature_symbols=["n_held"], states=[state], transitions=[], cycle=Cycle(vertex_indices=(3,), state_indices=(10,)), dicts=dicts, ext=True)
    psv = render_document(doc, "psv")
    assert "[states]\nvertex|state|module|memory|flags|f0\nv3|s10|M0|m0|CYCLE|1" in psv
    assert "cycle_vertex_indices|v3" in psv


def test_ext_successors_carry_module_and_memory():
    dicts = Dictionaries(ext=True)
    dicts.rule("load0")  # r0
    successors = [
        # a taken move lands in module M's memory state; a gap leaves mod/mem blank
        Successor(src=5, target=WitnessState(7, {"n": 1}, memory=("gripper", "carry")), action="(move a b)", rule="load0", delta={}),
        Successor(src=5, target=WitnessState(8, {"n": 2}, flags=("GOAL",)), action="(move a c)", rule=None, delta={}),
    ]
    doc = successors_document(header=[("id", "s")], feature_symbols=["n"], successors=successors, dicts=dicts, ext=True)
    psv = render_document(doc, "psv")
    assert "[successors]\nsource|action|target|rule|module|memory|flags|delta" in psv
    assert "s5|a0|s7|r0|M0|m0||" in psv
    assert "s5|a1|s8||||GOAL|" in psv
