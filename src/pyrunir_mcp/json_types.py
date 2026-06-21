from __future__ import annotations

from typing import TypeAlias

JsonValue: TypeAlias = bool | int | float | str | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
JsonDictList: TypeAlias = list[JsonObject]
