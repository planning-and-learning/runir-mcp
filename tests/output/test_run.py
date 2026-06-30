from pyrunir_mcp.output.run import RunCategory, RunStatus, build_run_envelope, status_category


def test_status_category_maps_proof_statuses():
    assert status_category("SUCCESS") is RunCategory.SUCCESS
    assert status_category("OUT_OF_TIME") is RunCategory.TIMEOUT
    assert status_category("OUT_OF_STATES") is RunCategory.RESOURCE_LIMIT
    assert status_category("OUT_OF_MEMORY") is RunCategory.RESOURCE_LIMIT
    assert status_category("FAILURE") is RunCategory.COUNTEREXAMPLE
    assert status_category("anything else") is RunCategory.COUNTEREXAMPLE


def _envelope(tmp_path, name, **kwargs):
    return build_run_envelope(
        tool="t",
        output_dir=tmp_path / name,
        metadata={},
        dictionary_tables={},
        artifacts={},
        items=[],
        **kwargs,
    )


def test_primary_carries_category_and_status(tmp_path):
    # A successful run must report category "success" so consumers (e.g. lgp) accept the proof
    # instead of misreading the absence of a category as a counterexample.
    success = _envelope(tmp_path, "ok", status=RunStatus.SUCCESS)["primary"]
    assert success["category"] == "success"
    assert success["status"] == "success"
    assert success["successful"] is True

    # An explicit category (prove passes the granular proof status) is preserved.
    assert (
        _envelope(tmp_path, "to", status=RunStatus.FAILURE, category=RunCategory.TIMEOUT)[
            "primary"
        ]["category"]
        == "timeout"
    )

    # A failure without an explicit category defaults to a counterexample.
    assert (
        _envelope(tmp_path, "ce", status=RunStatus.FAILURE)["primary"]["category"]
        == "counterexample"
    )
