"""Output-directory reservation.

Each tool writes its run under an `output_dir`; this reserves that directory (or allocates a
numbered child) so a new run never overwrites a previous one. The actual artifacts are written
by `output.writer`/`output.run`.
"""

from __future__ import annotations

from pathlib import Path

RESERVATION_MARKER = ".pyrunir-mcp-output"

# Names that indicate a directory already holds a previous run's output.
_RUN_OUTPUT_NAMES = (
    RESERVATION_MARKER,
    "manifest.json",
    "summary.psv",
    "failures.psv",
    "dicts",
    "failures",
)


def _has_existing_run_output(output_dir: Path) -> bool:
    return any((output_dir / name).exists() for name in _RUN_OUTPUT_NAMES)


def _reserve_output_dir(output_dir: Path) -> bool:
    output_dir.mkdir(parents=True, exist_ok=True)
    if _has_existing_run_output(output_dir):
        return False
    try:
        with (output_dir / RESERVATION_MARKER).open("x", encoding="utf-8") as fh:
            fh.write("reserved\n")
    except FileExistsError:
        return False
    return True


def fresh_output_dir(output_dir: Path) -> Path:
    """Return an output dir that will not overwrite a previous run.

    App orchestration often pre-creates an empty trial directory before invoking a tool; that
    remains the primary output dir. If the same directory already contains a prior run, allocate
    a numbered child under it so every call stays inspectable.
    """
    if _reserve_output_dir(output_dir):
        return output_dir
    for index in range(2, 10000):
        candidate = output_dir / f"run-{index:03d}"
        if _reserve_output_dir(candidate):
            return candidate
    raise RuntimeError(f"could not allocate fresh MCP output directory under {output_dir}")
