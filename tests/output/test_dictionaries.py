from pyrunir_mcp.output.dictionaries import Dictionaries, Dictionary


def test_intern_assigns_stable_ordered_aliases():
    d = Dictionary("f", ["symbol"])
    assert d.intern("a", ["a"]) == "f0"
    assert d.intern("b", ["b"]) == "f1"
    assert d.intern("a", ["a"]) == "f0"  # idempotent


def test_empty_dictionary_table_is_none():
    assert Dictionary("f", ["symbol"]).table("features") is None


def test_dictionary_table_shape():
    d = Dictionary("p", ["kind", "atom"])
    d.intern(("fluent", "at(a)"), ["fluent", "at(a)"])
    table = d.table("atoms")
    assert table.columns == ["id", "kind", "atom"]
    assert table.rows == [["p0", "fluent", "at(a)"]]


def test_dictionaries_base_rules_single_column():
    dicts = Dictionaries(ext=False)
    assert dicts.rule("pickup") == "r0"
    assert dicts.tables()["rules"].columns == ["id", "symbol"]


def test_dictionaries_ext_rules_carry_src_tgt():
    dicts = Dictionaries(ext=True)
    m0 = dicts.memory("deliver", "q_init", "initial")
    m1 = dicts.memory("deliver", "q_done", "accepting")
    assert dicts.rule("advance", m0, m1) == "r0"
    tables = dicts.tables()
    assert tables["rules"].columns == ["id", "symbol", "src", "tgt"]
    assert tables["rules"].rows == [["r0", "advance", "m0", "m1"]]
    assert tables["memory"].rows == [["m0", "deliver", "q_init", "initial"], ["m1", "deliver", "q_done", "accepting"]]


def test_dictionaries_omits_empty_tables():
    dicts = Dictionaries(ext=False)
    dicts.feature("b_holding")
    dicts.atom("fluent", "at(a)")
    assert set(dicts.tables()) == {"features", "atoms"}  # no rules/actions/memory


def test_feature_and_atom_dedup():
    dicts = Dictionaries()
    assert dicts.feature("x") == dicts.feature("x") == "f0"
    assert dicts.atom("fluent", "at(a)") == "p0"
    assert dicts.atom("derived", "at(a)") == "p1"  # kind is part of the key
