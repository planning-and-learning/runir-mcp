from __future__ import annotations

from pyrunir_mcp.kr.ps.feature_evidence import json_value


def test_json_value_serializes_uint32_max_as_inf():
    assert json_value(2**32 - 1) == "inf"
