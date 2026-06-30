from __future__ import annotations

import tomllib
from pathlib import Path


def _pyproject() -> dict:
    return tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())


def test_package_declares_no_console_scripts() -> None:
    project = _pyproject()["project"]
    assert "scripts" not in project


def test_package_declares_typed_api() -> None:
    marker = Path(__file__).resolve().parents[1] / "src" / "pyrunir_mcp" / "py.typed"
    assert marker.is_file()


def test_package_version_matches_project_metadata() -> None:
    import pyrunir_mcp

    assert pyrunir_mcp.__version__ == _pyproject()["project"]["version"]
