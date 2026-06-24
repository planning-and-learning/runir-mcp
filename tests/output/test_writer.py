import pytest

from pyrunir_mcp.output.writer import DEFAULT_FORMATS, FORMAT_ENV, resolve_formats, write_run
from pyrunir_mcp.tables import Document, Table


def test_write_run_emits_all_formats_and_nests(tmp_path):
    artifacts = {
        "summary": Table(name="summary", columns=["a", "b"], rows=[[1, 2]]),
        "counterexamples/cycle/cycle-001": Document(
            header=[("tool", "execute_policy")],
            sections=[Table(name="states", columns=["idx"], rows=[[0]])],
        ),
    }
    primary = write_run(tmp_path, artifacts)

    for ext in ("psv", "md", "json"):
        assert (tmp_path / f"summary.{ext}").exists()
        assert (tmp_path / "counterexamples" / "cycle" / f"cycle-001.{ext}").exists()

    assert primary["summary"] == (tmp_path / "summary.psv").resolve().as_posix()
    assert (tmp_path / "summary.psv").read_text() == "a|b\n1|2\n"


def test_write_run_respects_format_subset(tmp_path):
    artifacts = {"summary": Table(name="summary", columns=["a"], rows=[[1]])}
    write_run(tmp_path, artifacts, formats=("psv",))
    assert (tmp_path / "summary.psv").exists()
    assert not (tmp_path / "summary.md").exists()
    assert not (tmp_path / "summary.json").exists()


def test_resolve_formats_explicit_wins_over_env(monkeypatch):
    monkeypatch.setenv(FORMAT_ENV, "md")
    assert resolve_formats(("psv",)) == ("psv",)


def test_resolve_formats_from_env(monkeypatch):
    monkeypatch.delenv(FORMAT_ENV, raising=False)
    assert resolve_formats() == DEFAULT_FORMATS
    monkeypatch.setenv(FORMAT_ENV, "all")
    assert resolve_formats() == DEFAULT_FORMATS
    for fmt in ("psv", "md", "json"):
        monkeypatch.setenv(FORMAT_ENV, fmt)
        assert resolve_formats() == (fmt,)
    monkeypatch.setenv(FORMAT_ENV, "xml")
    with pytest.raises(ValueError):
        resolve_formats()


def test_write_run_uses_env_single_format(tmp_path, monkeypatch):
    monkeypatch.setenv(FORMAT_ENV, "md")
    write_run(tmp_path, {"summary": Table(name="summary", columns=["a"], rows=[[1]])})
    assert (tmp_path / "summary.md").exists()
    assert not (tmp_path / "summary.psv").exists()
    assert not (tmp_path / "summary.json").exists()
