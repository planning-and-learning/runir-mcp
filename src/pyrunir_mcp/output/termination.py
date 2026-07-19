"""Build the structural-termination non-termination witness (a cycle in the termination graph).

Abstract vertices carry Boolean/numerical variables; edges carry the numerical
changes they cause. We report the cycle and the changes as-is, without judging which measure
ought to decrease.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyrunir_mcp.enums import VariableKind
from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.keys import (
    Keys,
    TableColumns,
)
from pyrunir_mcp.output.dictionaries import Dictionary
from pyrunir_mcp.tables import Document, Table


def _str_dict() -> dict[str, str]:
    return {}


def _bool_dict() -> dict[str, bool]:
    return {}


VARIABLE_KINDS = (VariableKind.BOOLEAN, VariableKind.NUMERICAL)


@dataclass(frozen=True)
class TerminationVertex:
    index: int
    memory_state: str | None
    booleans: dict[str, bool] = field(default_factory=_bool_dict)
    numericals: dict[str, bool] = field(default_factory=_bool_dict)

    def values(self) -> dict[VariableKind, dict[str, bool]]:
        return {
            VariableKind.BOOLEAN: self.booleans,
            VariableKind.NUMERICAL: self.numericals,
        }


@dataclass(frozen=True)
class TerminationEdge:
    index: int
    source: int
    target: int
    rule: str
    boolean_changes: dict[str, str] = field(default_factory=_str_dict)
    numerical_changes: dict[str, str] = field(default_factory=_str_dict)


class TerminationDictionaries:
    def __init__(self) -> None:
        self.variables = Dictionary("v", [Keys.KIND, Keys.SYMBOL])
        self.memories = Dictionary("m", [Keys.MEMORY])
        self.rules = Dictionary("r", [Keys.SYMBOL])

    def variable(self, kind: VariableKind, symbol: str) -> str:
        return self.variables.intern((kind, symbol), [kind.value, symbol])

    def memory(self, memory: str) -> str:
        return self.memories.intern(memory, [memory])

    def rule(self, symbol: str) -> str:
        return self.rules.intern(symbol, [symbol])

    def tables(self, *, include_memory: bool = True) -> dict[str, Table]:
        named = {Keys.VARIABLES: self.variables, Keys.RULES: self.rules}
        if include_memory:
            named[Keys.MEMORY] = self.memories
        tables: dict[str, Table] = {}
        for name, dictionary in named.items():
            table = dictionary.table(name, include_empty=True)
            assert table is not None
            tables[name] = table
        return tables


def _ordered_variables(vertex: TerminationVertex) -> list[tuple[VariableKind, str]]:
    values = vertex.values()
    return [(kind, name) for kind in VARIABLE_KINDS for name in values[kind]]


def counterexample_document(
    *,
    header: list[tuple[str, str]],
    vertices: list[TerminationVertex],
    edges: list[TerminationEdge],
    dicts: TerminationDictionaries,
    include_memory: bool = True,
) -> Document:
    variables = _ordered_variables(vertices[0]) if vertices else []
    aliases = [dicts.variable(kind, name) for kind, name in variables]

    vertex_rows: list[list[JsonValue]] = []
    for vertex in vertices:
        values = vertex.values()
        valuation = " ".join(
            alias if values[kind][name] else f"¬{alias}"
            for (kind, name), alias in zip(variables, aliases, strict=True)
        )
        if include_memory:
            if vertex.memory_state is None:
                raise ValueError("termination vertex is missing its memory state")
            vertex_rows.append([vertex.index, dicts.memory(vertex.memory_state), valuation])
        else:
            vertex_rows.append([vertex.index, valuation])

    edge_rows: list[list[JsonValue]] = []
    for edge in edges:
        changes = " ".join(
            f"{dicts.variable(kind, name)}{change}"
            for kind, values in (
                (VariableKind.BOOLEAN, edge.boolean_changes),
                (VariableKind.NUMERICAL, edge.numerical_changes),
            )
            for name, change in values.items()
        )
        edge_rows.append([edge.index, edge.source, edge.target, dicts.rule(edge.rule), changes])

    return Document(
        header=header,
        sections=[
            Table(
                name=Keys.VERTICES,
                columns=[
                    TableColumns.VERTEX_INDEX,
                    *([TableColumns.MEMORY_ID] if include_memory else []),
                    TableColumns.VALUATION,
                ],
                rows=vertex_rows,
            ),
            Table(name=Keys.EDGES, columns=[TableColumns.EDGE_INDEX, TableColumns.SOURCE_VERTEX_INDEX, TableColumns.TARGET_VERTEX_INDEX, TableColumns.RULE_ID, TableColumns.DELTAS], rows=edge_rows),
        ],
    )
