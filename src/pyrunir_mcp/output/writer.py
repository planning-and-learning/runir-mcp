"""Write run artifacts to disk in each configured format."""

from __future__ import annotations

from pathlib import Path

from pyrunir_mcp.tables import Document, Fmt, Table, render, render_document

DEFAULT_FORMATS: tuple[Fmt, ...] = ("psv", "md", "json")

Artifact = Table | Document


def _render(artifact: Artifact, fmt: Fmt) -> str:
    if isinstance(artifact, Document):
        return render_document(artifact, fmt)
    return render(artifact, fmt)


def write_run(
    output_dir: Path,
    artifacts: dict[str, Artifact],
    formats: tuple[Fmt, ...] = DEFAULT_FORMATS,
) -> dict[str, str]:
    """Render every artifact in every format under `output_dir`.

    `artifacts` maps a logical name (may contain `/` to nest, e.g.
    `counterexamples/cycle/cycle-001`) to a `Table` or `Document`. Returns each logical name
    mapped to its primary (first-format) absolute path, for the manifest/envelope to reference.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    primary_paths: dict[str, str] = {}
    for name, artifact in artifacts.items():
        for fmt in formats:
            path = output_dir / f"{name}.{fmt}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render(artifact, fmt) + "\n", encoding="utf-8")
        primary_paths[name] = (output_dir / f"{name}.{formats[0]}").resolve().as_posix()
    return primary_paths
