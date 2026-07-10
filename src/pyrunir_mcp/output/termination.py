"""Build the structural-termination non-termination witness (a cycle in the termination graph).

Abstract vertices carry concept/boolean/numerical variables; edges carry the numerical
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


VARIABLE_KINDS = (VariableKind.CONCEPT, VariableKind.BOOLEAN, VariableKind.NUMERICAL)


@dataclass(frozen=True)
class TerminationVertex:
    index: int
    memory_state: str
    concepts: dict[str, str] = field(default_factory=_str_dict)
    booleans: dict[str, str] = field(default_factory=_str_dict)
    numericals: dict[str, str] = field(default_factory=_str_dict)

    def values(self) -> dict[VariableKind, dict[str, str]]:
        return {
            VariableKind.CONCEPT: self.concepts,
            VariableKind.BOOLEAN: self.booleans,
            VariableKind.NUMERICAL: self.numericals,
        }


@dataclass(frozen=True)
class TerminationEdge:
    index: int
    source: int
    target: int
    rule: str
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

    def tables(self) -> dict[str, Table]:
        named = {Keys.VARIABLES: self.variables, Keys.MEMORY: self.memories, Keys.RULES: self.rules}
        tables: dict[str, Table] = {}
        for name, dictionary in named.items():
            table = dictionary.table(name, include_empty=True)
            assert table is not None
            tables[name] = table
        return tables


def _ordered_variables(vertex: TerminationVertex) -> list[tuple[VariableKind, str]]:
    values = vertex.values()
    return [(kind, name) for kind in VARIABLE_KINDS for name in values[kind]]


def _cycle_table(edges: list[TerminationEdge]) -> Table:
    if edges:
        vertices = [edges[0].source, *(edge.target for edge in edges)]
        edge_indices = [edge.index for edge in edges]
    else:
        vertices, edge_indices = [], []
    return Table(
        name=Keys.CYCLE,
        columns=[TableColumns.VERTEX_INDICES, TableColumns.EDGE_INDICES],
        rows=[[",".join(map(str, vertices)), ",".join(map(str, edge_indices))]],
    )


def counterexample_document(
    *,
    header: list[tuple[str, str]],
    vertices: list[TerminationVertex],
    edges: list[TerminationEdge],
    dicts: TerminationDictionaries,
) -> Document:
    variables = _ordered_variables(vertices[0]) if vertices else []
    aliases = [dicts.variable(kind, name) for kind, name in variables]

    vertex_rows: list[list[JsonValue]] = []
    for vertex in vertices:
        values = vertex.values()
        cells = [values[kind].get(name, "") for kind, name in variables]
        vertex_rows.append([vertex.index, dicts.memory(vertex.memory_state), *cells])

    edge_rows: list[list[JsonValue]] = []
    for edge in edges:
        changes = " ".join(
            f"{dicts.variable(VariableKind.NUMERICAL, name)}:{change}"
            for name, change in edge.numerical_changes.items()
        )
        edge_rows.append([edge.index, edge.source, edge.target, dicts.rule(edge.rule), changes])

    return Document(
        header=header,
        sections=[
            _cycle_table(edges),
            Table(name=Keys.VERTICES, columns=[TableColumns.VERTEX_INDEX, TableColumns.MEMORY_ID, *aliases], rows=vertex_rows),
            Table(name=Keys.EDGES, columns=[TableColumns.EDGE_INDEX, TableColumns.SOURCE_VERTEX_INDEX, TableColumns.TARGET_VERTEX_INDEX, TableColumns.RULE_ID, TableColumns.DELTAS], rows=edge_rows),
        ],
    )
