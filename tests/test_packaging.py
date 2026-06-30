from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

from pyrunir_mcp.json_types import JsonObject


def _pyproject() -> JsonObject:
    return cast(JsonObject, tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()))


def test_package_declares_no_console_scripts() -> None:
    project = cast(JsonObject, _pyproject()["project"])
    assert "scripts" not in project


def test_package_declares_typed_api() -> None:
    marker = Path(__file__).resolve().parents[1] / "src" / "pyrunir_mcp" / "py.typed"
    assert marker.is_file()


def test_package_version_matches_project_metadata() -> None:
    import pyrunir_mcp

    project = cast(JsonObject, _pyproject()["project"])
    assert pyrunir_mcp.__version__ == cast(str, project["version"])
