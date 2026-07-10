from __future__ import annotations

from typing import TypeAlias

UINT32_MAX_SENTINEL = 2**32 - 1
INFINITY_SENTINEL = "inf"

JsonValue: TypeAlias = bool | int | float | str | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
JsonDictList: TypeAlias = list[JsonObject]


def normalize_json_value(value: JsonValue) -> JsonValue:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value == UINT32_MAX_SENTINEL:
        return INFINITY_SENTINEL
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_json_value(item) for key, item in value.items()}
    return value
