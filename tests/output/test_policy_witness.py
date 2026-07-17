from pyrunir_mcp.enums import AtomKind
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import (
    Successor,
    WitnessState,
    WitnessTransition,
    counterexample_document,
    resolve_flags,
    successors_document,
    witness_trace_document,
)
from pyrunir_mcp.tables import render_document

HEADER = [
    ("tool", "runir.ps.find_solution"),
    ("id", "cycle-001"),
    ("category", "cycle"),
    ("status", "cycle"),
    ("task_file", "p01.pddl"),
]
FEATURES = ["n_undeliv", "n_held", "b_atgoal"]


def test_resolve_flags():
    assert resolve_flags(initial=True) == ("init",)
    assert resolve_flags(deadend=True) == ("deadend",)
    assert resolve_flags(witness=True, cycle=True) == ("witness", "cycle")
    assert resolve_flags() == ()


def test_witness_trace_document_matches_doc():
    dicts = Dictionaries()
    dicts.rule("pickup_r1")
    dicts.rule("deliver_r2")
    states = [
        WitnessState(
            0,
            {"n_undeliv": 3, "n_held": 0, "b_atgoal": False},
            fluent=("at(robot roomA)",),
            flags=("init",),
        ),
        WitnessState(
            1, {"n_undeliv": 2, "n_held": 1, "b_atgoal": False}, fluent=("holding(ball1)",)
        ),
        WitnessState(2, {"n_undeliv": 2, "n_held": 0, "b_atgoal": False}, flags=("cycle",)),
    ]
    transitions = [
        WitnessTransition(
            0,
            0,
            1,
            action="(pickup ball1 roomA)",
            rule="pickup_r1",
            delta={"n_held": (0, 1)},
        ),
        WitnessTransition(
            1,
            1,
            2,
            action="(drop ball1 roomB)",
            rule="deliver_r2",
            delta={"n_undeliv": (3, 2), "n_held": (1, 0)},
        ),
    ]
    doc = witness_trace_document(
        header=HEADER,
        feature_symbols=FEATURES,
        states=states,
        transitions=transitions,
        dicts=dicts,
        ext=False,
    )
    assert render_document(doc, "psv") == (
        "@tool runir.ps.find_solution\n@id cycle-001\n@category cycle\n@status cycle\n@task_file p01.pddl\n"
        "\n[states]\nstate_id|flags|hstar|hlmcut|f0|f1|f2\ns0|init|||3|0|F\ns1||||2|1|F\ns2|cycle|||2|0|F\n"
        "\n[transitions]\nstep|source_state_id|target_state_id|rule_id|action_id|deltas\n0|s0|s1|r0|a0|f1:0>1\n1|s1|s2|r1|a1|f0:3>2 f1:1>0\n"
        "\n[facts]\nstate_id|atom_ids\ns0|p0\ns1|p1"
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
    dicts.atom(AtomKind.FLUENT, "at(robot roomA)")
    dicts.atom(AtomKind.FLUENT, "holding(ball1)")
    states = [
        WitnessState(
            1,
            {"n_undeliv": 2, "n_held": 1, "b_atgoal": False},
            fluent=("holding(ball1)",),
            flags=("cycle",),
        ),
        WitnessState(
            2,
            {"n_undeliv": 2, "n_held": 0, "b_atgoal": False},
            fluent=("at(robot roomA)",),
            flags=("cycle",),
        ),
    ]
    transitions = [
        WitnessTransition(
            0, 1, 2, action="(drop ball1 roomB)", rule="deliver_r2", delta={"n_held": (1, 0)}
        ),
        WitnessTransition(
            1, 2, 1, action="(pickup ball1 roomA)", rule="pickup_r1", delta={"n_held": (0, 1)}
        ),
    ]
    cycle = True
    doc = counterexample_document(
        header=HEADER,
        feature_symbols=FEATURES,
        states=states,
        transitions=transitions,
        cycle=cycle,
        dicts=dicts,
        ext=False,
    )
    assert render_document(doc, "psv") == (
        "@tool runir.ps.find_solution\n@id cycle-001\n@category cycle\n@status cycle\n@task_file p01.pddl\n"
        "\n[states]\nstate_id|flags|hstar|hlmcut|f0|f1|f2\ns1|cycle|||2|1|F\ns2|cycle|||2|0|F\ns1|cycle|||2|1|F\n"
        "\n[transitions]\nstep|source_state_id|target_state_id|rule_id|action_id|deltas\n0|s1|s2|r1|a1|f1:1>0\n1|s2|s1|r0|a0|f1:0>1\n"
        "\n[facts]\nstate_id|atom_ids\ns1|p1\ns2|p0"
    )


def test_cycle_counterexample_rotates_smallest_base_state_first():
    dicts = Dictionaries()
    states = [
        WitnessState(3, {"n": 3}, flags=("cycle",)),
        WitnessState(1, {"n": 1}, flags=("cycle",)),
        WitnessState(2, {"n": 2}, flags=("cycle",)),
    ]
    transitions = [
        WitnessTransition(0, 3, 1, action="a31", delta={"n": (3, 1)}),
        WitnessTransition(1, 1, 2, action="a12", delta={"n": (1, 2)}),
        WitnessTransition(2, 2, 3, action="a23", delta={"n": (2, 3)}),
    ]
    doc = counterexample_document(
        header=[],
        feature_symbols=["n"],
        states=states,
        transitions=transitions,
        cycle=True,
        dicts=dicts,
        ext=False,
    )
    psv = render_document(doc, "psv")
    assert "[states]\nstate_id|flags|hstar|hlmcut|f0\ns1|cycle|||1\ns2|cycle|||2\ns3|cycle|||3\ns1|cycle|||1" in psv
    assert "[transitions]\nstep|source_state_id|target_state_id|rule_id|action_id|deltas\n0|s1|s2||a0|f0:1>2\n1|s2|s3||a1|f0:2>3\n2|s3|s1||a2|f0:3>1" in psv


def test_ext_cycle_counterexample_rotates_by_module_memory_state_triple():
    dicts = Dictionaries(ext=True)
    states = [
        WitnessState(1, {"n": 1}, flags=("cycle",), memory=("z", "m0")),
        WitnessState(0, {"n": 0}, flags=("cycle",), memory=("a", "m2")),
        WitnessState(2, {"n": 2}, flags=("cycle",), memory=("a", "m1")),
    ]
    transitions = [
        WitnessTransition(
            0, 1, 0, source_memory=("z", "m0"), target_memory=("a", "m2"), action="a10", delta={"n": (1, 0)}
        ),
        WitnessTransition(
            1, 0, 2, source_memory=("a", "m2"), target_memory=("a", "m1"), action="a02", delta={"n": (0, 2)}
        ),
        WitnessTransition(
            2, 2, 1, source_memory=("a", "m1"), target_memory=("z", "m0"), action="a21", delta={"n": (2, 1)}
        ),
    ]
    doc = counterexample_document(
        header=[],
        feature_symbols=["n"],
        states=states,
        transitions=transitions,
        cycle=True,
        dicts=dicts,
        ext=True,
    )
    psv = render_document(doc, "psv")
    assert "[states]\nstate_id|module_id|memory_id|flags|hstar|hlmcut|f0\ns2|M0|m0|cycle|||2\ns1|M1|m1|cycle|||1\ns0|M0|m2|cycle|||0\ns2|M0|m0|cycle|||2" in psv
    assert "[transitions]\nstep|source_state_id|source_module_id|source_memory_id|target_state_id|target_module_id|target_memory_id|rule_id|action_id|deltas\n0|s2|M0|m0|s1|M1|m1||a0|f0:2>1\n1|s1|M1|m1|s0|M0|m2||a1|f0:1>0\n2|s0|M0|m2|s2|M0|m0||a2|f0:0>2" in psv


def test_state_witness_uses_states_section():
    dicts = Dictionaries()
    state = WitnessState(
        42, {"n_undeliv": 3}, fluent=("at(robot roomA)",), flags=("open", "witness")
    )
    doc = counterexample_document(
        header=[("id", "open-001")],
        feature_symbols=["n_undeliv"],
        states=[state],
        transitions=[],
        cycle=False,
        dicts=dicts,
        ext=False,
    )
    psv = render_document(doc, "psv")
    assert "[states]\nstate_id|flags|hstar|hlmcut|f0\ns42|open,witness|||3" in psv
    assert "[state]" not in psv


def test_successors_document_shows_empty_rule_gap():
    dicts = Dictionaries()
    dicts.rule("deliver_r2")  # r0
    successors = [
        Successor(
            src=1,
            target=WitnessState(60, {"n_undeliv": 1}, flags=("goal",)),
            action="(deliver ball1)",
            rule=None,
            delta={"n_undeliv": (2, 1)},
        ),
        Successor(
            src=2,
            target=WitnessState(61, {"n_undeliv": 3}, flags=("deadend",)),
            action="(drop ball1)",
            rule="deliver_r2",
            delta={"n_undeliv": (2, 3)},
        ),
    ]
    doc = successors_document(
        header=[("id", "cycle-001")],
        feature_symbols=["n_undeliv"],
        successors=successors,
        dicts=dicts,
        ext=False,
    )
    psv = render_document(doc, "psv")
    # goal-reaching escape with empty rule cell = the missing-guidance gap
    assert "s1|a0|s60||goal|f0:2>1" in psv
    assert "[states]\nstate_id|flags|hstar|hlmcut|f0" in psv
    assert "s2|a1|s61|r0|deadend|f0:2>3" in psv


def test_successors_document_includes_source_state_once_with_facts():
    source = WitnessState(0, {"n": 2}, fluent=("at(a)",), flags=("open", "witness"))
    successors = [
        Successor(src=0, source=source, target=WitnessState(1, {"n": 1}, fluent=("at(b)",)), action="move(a,b)"),
        Successor(src=0, source=source, target=WitnessState(0, {"n": 2}, fluent=("at(a)",)), action="wait"),
    ]
    doc = successors_document(
        header=[("id", "successors-001")],
        feature_symbols=["n"],
        successors=successors,
        dicts=Dictionaries(),
        ext=False,
    )
    psv = render_document(doc, "psv")
    assert psv.count("\ns0|open,witness|||2") == 1
    assert "[facts]\nstate_id|atom_ids\ns0|p0\ns1|p1" in psv


def test_base_state_columns_can_include_hlmcut_without_hstar():
    state = WitnessState(1, {"n_undeliv": 2}, hstar=7, hlmcut=3)
    doc = counterexample_document(
        header=[("id", "open-001")],
        feature_symbols=["n_undeliv"],
        states=[state],
        transitions=[],
        cycle=False,
        dicts=Dictionaries(),
        ext=False,
        include_hstar=False,
        include_hlmcut=True,
    )
    psv = render_document(doc, "psv")
    assert "[states]\nstate_id|flags|hlmcut|f0\ns1||3|2" in psv
    assert "hstar" not in psv


def test_ext_state_columns_can_include_hstar_without_hlmcut():
    state = WitnessState(2, {"n_held": 1}, hstar=5, hlmcut=2, memory=("m", "q"))
    doc = counterexample_document(
        header=[("id", "cycle-001")],
        feature_symbols=["n_held"],
        states=[state],
        transitions=[],
        cycle=True,
        dicts=Dictionaries(ext=True),
        ext=True,
        include_hstar=True,
        include_hlmcut=False,
    )
    psv = render_document(doc, "psv")
    assert "[states]\nstate_id|module_id|memory_id|flags|hstar|f0\ns2|M0|m0||5|1\ns2|M0|m0||5|1" in psv
    assert "hlmcut" not in psv


def test_ext_successor_state_columns_include_hlmcut_by_default():
    succ = Successor(src=0, target=WitnessState(1, {"n": 9}, hstar="", hlmcut=4), action="(a)")
    doc = successors_document(
        header=[("id", "successors-001")],
        feature_symbols=["n"],
        successors=[succ],
        dicts=Dictionaries(ext=True),
        ext=True,
    )
    psv = render_document(doc, "psv")
    assert "[states]\nstate_id|flags|hstar|hlmcut|f0\ns0||||\ns1|||4|9" in psv


def test_ext_state_columns_include_mod_and_mem_without_vertex():
    dicts = Dictionaries(ext=True)
    mem = ("deliver", "q_init")  # (module, memory)
    state = WitnessState(10, {"n_held": 1}, flags=("cycle",), memory=mem)
    doc = counterexample_document(
        header=[("id", "c")],
        feature_symbols=["n_held"],
        states=[state],
        transitions=[],
        cycle=True,
        dicts=dicts,
        ext=True,
    )
    psv = render_document(doc, "psv")
    assert "[states]\nstate_id|module_id|memory_id|flags|hstar|hlmcut|f0\ns10|M0|m0|cycle|||1\ns10|M0|m0|cycle|||1" in psv
    assert "[cycle]" not in psv


def test_ext_successors_carry_module_and_memory():
    dicts = Dictionaries(ext=True)
    dicts.rule("load0")  # r0
    successors = [
        # a taken move lands in module M's memory state; a gap leaves mod/mem blank
        Successor(
            src=5,
            source_memory=("gripper", "free"),
            target=WitnessState(7, {"n": 1}, memory=("gripper", "carry")),
            action="(move a b)",
            rule="load0",
            delta={"n": (0, 1)},
        ),
        Successor(
            src=5,
            source_memory=("gripper", "free"),
            target=WitnessState(8, {"n": 2}, flags=("goal",)),
            action="(move a c)",
            rule=None,
            delta={"n": (0, 2)},
        ),
    ]
    doc = successors_document(
        header=[("id", "s")], feature_symbols=["n"], successors=successors, dicts=dicts, ext=True
    )
    psv = render_document(doc, "psv")
    assert "[successors]\nsource_state_id|source_module_id|source_memory_id|action_id|target_state_id|target_module_id|target_memory_id|rule_id|flags|deltas" in psv
    assert "[states]\nstate_id|flags|hstar|hlmcut|f0" in psv
    assert "s5|M0|m0|a0|s7|M0|m1|r0||f0:0>1" in psv
    assert "s5|M0|m0|a1|s8||||goal|f0:0>2" in psv


def test_uint32_max_feature_values_render_as_inf_in_witness_and_delta():
    dicts = Dictionaries()
    doc = witness_trace_document(
        header=[],
        feature_symbols=["n"],
        states=[
            WitnessState(45, {"n": 2**32 - 1}),
            WitnessState(46, {"n": 1}),
        ],
        transitions=[WitnessTransition(0, 45, 46, delta={"n": (2**32 - 1, 1)})],
        dicts=dicts,
        ext=False,
    )

    psv = render_document(doc, "psv")
    assert "s45||||inf" in psv
    assert "f0:inf>1" in psv
