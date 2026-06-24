"""Write run artifacts to disk in each configured format."""

from __future__ import annotations

import os
from pathlib import Path

from pyrunir_mcp.tables import Document, Fmt, Table, render, render_document

DEFAULT_FORMATS: tuple[Fmt, ...] = ("psv", "md", "json")
FORMAT_ENV = "PYRUNIR_MCP_OUTPUT_FORMAT"

Artifact = Table | Document


def resolve_formats(formats: tuple[Fmt, ...] | None = None) -> tuple[Fmt, ...]:
    """The output formats to write. An explicit `formats` wins; otherwise the global
    `PYRUNIR_MCP_OUTPUT_FORMAT` env var picks a single format (`psv`/`md`/`json`) so a reader sees
    exactly one file per artifact (no adjacent duplicates), while `all`/unset writes every format
    (the default)."""
    if formats is not None:
        return formats
    choice = os.environ.get(FORMAT_ENV, "all").strip().lower()
    if choice in ("", "all"):
        return DEFAULT_FORMATS
    if choice == "psv":
        return ("psv",)
    if choice == "md":
        return ("md",)
    if choice == "json":
        return ("json",)
    raise ValueError(f"{FORMAT_ENV} must be one of: psv, md, json, all (got {choice!r}).")


def _render(artifact: Artifact, fmt: Fmt) -> str:
    if isinstance(artifact, Document):
        return render_document(artifact, fmt)
    return render(artifact, fmt)


def write_run(
    output_dir: Path,
    artifacts: dict[str, Artifact],
    formats: tuple[Fmt, ...] | None = None,
) -> dict[str, str]:
    """Render every artifact in each configured format under `output_dir`.

    `formats` defaults to the `PYRUNIR_MCP_OUTPUT_FORMAT` selection (see `resolve_formats`).
    `artifacts` maps a logical name (may contain `/` to nest, e.g.
    `counterexamples/cycle/cycle-001`) to a `Table` or `Document`. Returns each logical name
    mapped to its primary (first-format) absolute path, for the manifest/envelope to reference.
    """
    formats = resolve_formats(formats)
    output_dir.mkdir(parents=True, exist_ok=True)
    primary_paths: dict[str, str] = {}
    for name, artifact in artifacts.items():
        for fmt in formats:
            path = output_dir / f"{name}.{fmt}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render(artifact, fmt) + "\n", encoding="utf-8")
        primary_paths[name] = (output_dir / f"{name}.{formats[0]}").resolve().as_posix()
    return primary_paths
