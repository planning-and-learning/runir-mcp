import json
from typing import cast

import pytest

from pyrunir_mcp.tables import (
    Document,
    JSONRenderer,
    MarkdownRenderer,
    PSVRenderer,
    Renderer,
    Table,
    Fmt,
    render,
    render_document,
    renderer_for,
)


def _states_table() -> Table:
    return Table(
        name="states",
        columns=["idx", "n_undeliv", "n_held", "b_atgoal"],
        rows=[[0, 3, 0, False], [1, 2, 1, False]],
    )


def test_render_psv_table():
    psv = render(_states_table(), "psv")
    assert psv == (
        "idx|n_undeliv|n_held|b_atgoal\n"
        "0|3|0|F\n"
        "1|2|1|F"
    )


def test_render_markdown_table():
    md = render(_states_table(), "md")
    assert md == (
        "| idx | n_undeliv | n_held | b_atgoal |\n"
        "| --- | --------- | ------ | -------- |\n"
        "| 0   | 3         | 0      | F        |\n"
        "| 1   | 2         | 1      | F        |"
    )


def test_render_json_table_keeps_native_types():
    records = json.loads(render(_states_table(), "json"))
    assert records == [
        {"idx": 0, "n_undeliv": 3, "n_held": 0, "b_atgoal": False},
        {"idx": 1, "n_undeliv": 2, "n_held": 1, "b_atgoal": False},
    ]
    # bool stays bool in JSON, not "T"/"F"
    assert records[0]["b_atgoal"] is False


def test_bool_and_none_cells():
    table = Table(name="t", columns=["a", "b"], rows=[[True, None]])
    assert render(table, "psv") == "a|b\nT|"


def test_psv_rejects_pipe_in_cell():
    table = Table(name="t", columns=["a"], rows=[["cycle|x|y"]])
    with pytest.raises(ValueError):
        render(table, "psv")


def test_psv_rejects_newline_in_cell():
    table = Table(name="t", columns=["a"], rows=[["line1\nline2"]])
    with pytest.raises(ValueError):
        render(table, "psv")


def test_psv_rejects_pipe_in_column_name():
    table = Table(name="t", columns=["a|b"], rows=[])
    with pytest.raises(ValueError):
        render(table, "psv")


def test_markdown_escapes_pipe_in_column_name():
    table = Table(name="t", columns=["a|b"], rows=[])
    assert render(table, "md").startswith("| a\\|b |")


def test_markdown_escapes_pipe():
    table = Table(name="t", columns=["a"], rows=[["cycle|x"]])
    assert render(table, "md").endswith("| cycle\\|x |")


def test_render_document_psv_matches_spec_layout():
    doc = Document(
        header=[("tool", "execute_policy"), ("features", "a|b")],
        sections=[
            Table(name="states", columns=["idx", "a", "b"], rows=[[0, 3, False]]),
            Table(name="transitions", columns=["step", "src", "tgt"], rows=[[0, 0, 1]]),
        ],
    )
    assert render_document(doc, "psv") == (
        "@tool execute_policy\n"
        "@features a|b\n"
        "\n"
        "[states]\n"
        "idx|a|b\n"
        "0|3|F\n"
        "\n"
        "[transitions]\n"
        "step|src|tgt\n"
        "0|0|1"
    )


def test_render_document_json():
    doc = Document(
        header=[("tool", "execute_policy")],
        sections=[Table(name="states", columns=["idx", "a"], rows=[[0, 3]])],
    )
    parsed = json.loads(render_document(doc, "json"))
    assert parsed == {
        "header": {"tool": "execute_policy"},
        "sections": {"states": [{"idx": 0, "a": 3}]},
    }


def test_header_key_named_sections_does_not_collide():
    doc = Document(
        header=[("sections", "oops")],
        sections=[Table(name="states", columns=["a"], rows=[[1]])],
    )
    parsed = json.loads(render_document(doc, "json"))
    assert parsed["header"] == {"sections": "oops"}
    assert parsed["sections"] == {"states": [{"a": 1}]}


def test_table_rejects_row_length_mismatch():
    with pytest.raises(ValueError):
        Table(name="t", columns=["a", "b"], rows=[[1]])


def test_table_rejects_newline_in_name():
    with pytest.raises(ValueError):
        Table(name="bad\nname", columns=["a"], rows=[])


def test_psv_document_rejects_newline_in_header_value():
    doc = Document(header=[("problem", "p\n01")], sections=[])
    with pytest.raises(ValueError):
        render_document(doc, "psv")


def test_psv_document_rejects_bracket_in_section_name():
    doc = Document(header=[], sections=[Table(name="sta]tes", columns=["a"], rows=[[1]])])
    with pytest.raises(ValueError):
        render_document(doc, "psv")


def test_empty_table_psv_is_header_only():
    table = Table(name="t", columns=["a", "b"], rows=[])
    assert render(table, "psv") == "a|b"


def test_renderer_registry_returns_format_objects():
    assert isinstance(renderer_for("psv"), PSVRenderer)
    assert isinstance(renderer_for("md"), MarkdownRenderer)
    assert isinstance(renderer_for("json"), JSONRenderer)
    assert isinstance(renderer_for("psv"), Renderer)


def test_renderer_for_rejects_unknown_format():
    with pytest.raises(ValueError):
        renderer_for(cast(Fmt, "xml"))


def test_render_wrappers_match_renderer_objects():
    # The fmt-param convenience API and the renderer objects are the same path.
    assert render(_states_table(), "psv") == PSVRenderer().table(_states_table())
    doc = Document(header=[("tool", "x")], sections=[_states_table()])
    assert render_document(doc, "md") == MarkdownRenderer().document(doc)
