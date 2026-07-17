"""Write a native termination/classifier run and build the MCP result envelope.

The service builds the run-global dictionary tables and the per-witness artifacts; this module
writes them (plus a `summary` index) in every format and assembles the envelope that the MCP
layer returns. Solution searches use their richer `manifest.json` artifact path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir_mcp.artifacts import fresh_output_dir
from pyrunir_mcp.enums import ExecutionStatus, RunCategory, RunItemCategory, RunStatus
from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.keys import (
    Keys,
)
from pyrunir_mcp.output.writer import Artifact, write_run
from pyrunir_mcp.tables import Fmt, Table


@dataclass(frozen=True)
class RunItem:
    """One failure, referencing the artifact names written under failures/<id>/."""

    id: str
    category: RunItemCategory
    subject: str | None
    witness: str  # artifact name (e.g. "failures/cycle-001/witness")
    witness_trace: str | None = None  # artifact name, when a path witness trace exists
    successors: str | None = None  # artifact name, when successors were dumped
    plan_trace: str | None = None  # artifact name, when an open-state FF plan was dumped


def _summary_table(items: list[RunItem]) -> Table:
    return Table(
        name=Keys.SUMMARY,
        columns=[Keys.ID, Keys.CATEGORY, Keys.SUBJECT],
        rows=[[i.id, i.category.value, i.subject] for i in items],
    )


def _result_item(item: RunItem, paths: dict[str, str]) -> JsonObject:
    return {
        Keys.ID: item.id,
        Keys.CATEGORY: item.category.value,
        Keys.SUBJECT: item.subject,
        Keys.WITNESS_PATH: paths[item.witness],
        Keys.WITNESS_TRACE_PATH: paths[item.witness_trace] if item.witness_trace else None,
        Keys.SUCCESSORS_PATH: paths[item.successors] if item.successors else None,
        Keys.PLAN_TRACE_PATH: paths[item.plan_trace] if item.plan_trace else None,
    }


_STATUS_CATEGORY: dict[str, RunCategory] = {
    ExecutionStatus.SUCCESS: RunCategory.SUCCESS,
    ExecutionStatus.OUT_OF_TIME: RunCategory.OUT_OF_TIME,
    ExecutionStatus.OUT_OF_STATES: RunCategory.OUT_OF_STATES,
    ExecutionStatus.OUT_OF_MEMORY: RunCategory.OUT_OF_MEMORY,
    ExecutionStatus.FAILURE: RunCategory.COUNTEREXAMPLE,
}


def status_category(status_name: str) -> RunCategory:
    """Map a proof/execution status name to the exact run category consumers branch on.
    Resource-limit causes stay distinct so callers can group them as needed."""
    return _STATUS_CATEGORY.get(status_name.lower(), RunCategory.COUNTEREXAMPLE)


def build_run_envelope(
    *,
    tool: str,
    status: RunStatus,
    output_dir: Path,
    metadata: JsonObject,
    dictionary_tables: dict[str, Table],
    artifacts: dict[str, Artifact],
    items: list[RunItem],
    category: RunCategory | None = None,
    formats: tuple[Fmt, ...] | None = None,
) -> JsonObject:
    output_dir = fresh_output_dir(output_dir)
    # Dictionaries under dicts/; each failure's artifacts under failures/<id>/ (set by the caller).
    paths = write_run(
        output_dir,
        {
            **{f"dicts/{name}": table for name, table in dictionary_tables.items()},
            Keys.SUMMARY: _summary_table(items),
            **artifacts,
        },
        formats,
    )
    result_item_objects = [_result_item(item, paths) for item in items]
    result_items: list[JsonValue] = list(result_item_objects)
    output_path = output_dir.resolve().as_posix()
    passthrough: JsonObject = {
        key: metadata[key]
        for key in (
            Keys.PROGRAM_STATUS,
            Keys.INCOMPLETE_TERMINATION_STATUS,
            Keys.NONTERMINATING_MODULES,
        )
        if key in metadata
    }
    primary_doc: JsonObject = {
        Keys.STATUS: status.value,
        Keys.CATEGORY: (
            category
            or (RunCategory.SUCCESS if status is RunStatus.SUCCESS else RunCategory.COUNTEREXAMPLE)
        ).value,
        **passthrough,
    }
    return {
        Keys.SCHEMA_VERSION: 2,
        Keys.TOOL: tool,
        Keys.STATUS: status.value,
        Keys.PRIMARY: primary_doc,
        Keys.METADATA: metadata,
        Keys.ARTIFACTS: {Keys.SUMMARY: paths[Keys.SUMMARY]},
        Keys.COUNTEREXAMPLES: result_items,
        Keys.OUTPUT_DIR: output_path,
    }
