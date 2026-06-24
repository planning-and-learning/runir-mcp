from pyrunir_mcp.output.run import build_run_envelope, status_category


def test_status_category_maps_proof_statuses():
    assert status_category("SUCCESS") == "success"
    assert status_category("OUT_OF_TIME") == "timeout"
    assert status_category("OUT_OF_STATES") == "resource_limit"
    assert status_category("OUT_OF_MEMORY") == "resource_limit"
    assert status_category("FAILURE") == "counterexample"
    assert status_category("anything else") == "counterexample"


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
    success = _envelope(tmp_path, "ok", status="success")["primary"]
    assert success["category"] == "success"
    assert success["status"] == "success"
    assert success["successful"] is True

    # An explicit category (prove passes the granular proof status) is preserved.
    assert _envelope(tmp_path, "to", status="failure", category="timeout")["primary"]["category"] == "timeout"

    # A failure without an explicit category defaults to a counterexample.
    assert _envelope(tmp_path, "ce", status="failure")["primary"]["category"] == "counterexample"
