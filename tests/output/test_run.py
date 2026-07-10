from pathlib import Path
from typing import cast

from pyrunir_mcp.enums import RunCategory, RunStatus
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.output.run import build_run_envelope, status_category


def test_status_category_maps_proof_statuses() -> None:
    assert status_category("SUCCESS") is RunCategory.SUCCESS
    assert status_category("OUT_OF_TIME") is RunCategory.OUT_OF_TIME
    assert status_category("OUT_OF_STATES") is RunCategory.OUT_OF_STATES
    assert status_category("OUT_OF_MEMORY") is RunCategory.OUT_OF_MEMORY
    assert status_category("FAILURE") is RunCategory.COUNTEREXAMPLE
    assert status_category("anything else") is RunCategory.COUNTEREXAMPLE


def _envelope(
    tmp_path: Path,
    name: str,
    *,
    status: RunStatus = RunStatus.SUCCESS,
    category: RunCategory | None = None,
) -> JsonObject:
    return build_run_envelope(
        tool="t",
        output_dir=tmp_path / name,
        metadata={},
        dictionary_tables={},
        artifacts={},
        items=[],
        status=status,
        category=category,
    )


def _primary(envelope: JsonObject) -> JsonObject:
    return cast(JsonObject, envelope["primary"])


def test_primary_carries_category_and_status(tmp_path: Path) -> None:
    # A successful run must report category "success" so consumers (e.g. lgp) accept the proof
    # instead of misreading the absence of a category as a counterexample.
    success = _primary(_envelope(tmp_path, "ok", status=RunStatus.SUCCESS))
    assert success["category"] == "success"
    assert success["status"] == "success"

    # An explicit category (prove passes the granular proof status) is preserved.
    assert (
        _primary(
            _envelope(tmp_path, "to", status=RunStatus.FAILURE, category=RunCategory.OUT_OF_TIME)
        )["category"]
        == "out_of_time"
    )

    # A failure without an explicit category defaults to a counterexample.
    assert (
        _primary(_envelope(tmp_path, "ce", status=RunStatus.FAILURE))["category"]
        == "counterexample"
    )


def test_run_json_can_be_written_in_reserved_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    _envelope(tmp_path, "run")

    envelope = _envelope(tmp_path, "run")
    actual_output_dir = Path(cast(str, envelope["output_dir"]))
    run_json = actual_output_dir / "run.json"
    run_json.write_text("{}\n", encoding="utf-8")

    assert actual_output_dir == output_dir / "run-002"
    assert run_json.is_file()
    assert not (output_dir / "run.json").exists()
