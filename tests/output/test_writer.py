from pathlib import Path

import pytest

from pyrunir_mcp.output.writer import (
    DEFAULT_FORMATS,
    FORMAT_ENV,
    Artifact,
    resolve_formats,
    write_run,
)
from pyrunir_mcp.tables import Document, Table


def test_write_run_emits_all_formats_and_nests(tmp_path: Path) -> None:
    artifacts: dict[str, Artifact] = {
        "summary": Table(name="summary", columns=["a", "b"], rows=[[1, 2]]),
        "failures/cycle-001/witness": Document(
            header=[("tool", "runir.ps.find_solution")],
            sections=[Table(name="states", columns=["idx"], rows=[[0]])],
        ),
    }
    primary = write_run(tmp_path, artifacts)

    for ext in ("psv", "md", "json"):
        assert (tmp_path / f"summary.{ext}").exists()
        assert (tmp_path / "failures" / "cycle-001" / f"witness.{ext}").exists()

    assert primary["summary"] == (tmp_path / "summary.psv").resolve().as_posix()
    assert (tmp_path / "summary.psv").read_text() == "a|b\n1|2\n"


def test_write_run_respects_format_subset(tmp_path: Path) -> None:
    artifacts: dict[str, Artifact] = {"summary": Table(name="summary", columns=["a"], rows=[[1]])}
    write_run(tmp_path, artifacts, formats=("psv",))
    assert (tmp_path / "summary.psv").exists()
    assert not (tmp_path / "summary.md").exists()
    assert not (tmp_path / "summary.json").exists()


def test_resolve_formats_explicit_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FORMAT_ENV, "md")
    assert resolve_formats(("psv",)) == ("psv",)


def test_resolve_formats_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_write_run_uses_env_single_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FORMAT_ENV, "md")
    write_run(tmp_path, {"summary": Table(name="summary", columns=["a"], rows=[[1]])})
    assert (tmp_path / "summary.md").exists()
    assert not (tmp_path / "summary.psv").exists()
    assert not (tmp_path / "summary.json").exists()
