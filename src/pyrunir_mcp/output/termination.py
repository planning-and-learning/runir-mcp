"""Build the structural-termination non-termination witness (a cycle in the termination graph).

Abstract vertices carry concept/boolean/numerical variables; edges carry the numerical
changes they cause. We report the cycle and the changes as-is, without judging which measure
ought to decrease. See docs/output/runir.ps.ext.prove_termination.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.output.dictionaries import Dictionary
from pyrunir_mcp.tables import Document, Table

VARIABLE_KINDS = ("concept", "boolean", "numerical")


@dataclass(frozen=True)
class TerminationVertex:
    index: int
    memory_state: str
    concepts: dict[str, str] = field(default_factory=dict)
    booleans: dict[str, str] = field(default_factory=dict)
    numericals: dict[str, str] = field(default_factory=dict)

    def values(self) -> dict[str, dict[str, str]]:
        return {"concept": self.concepts, "boolean": self.booleans, "numerical": self.numericals}


@dataclass(frozen=True)
class TerminationEdge:
    index: int
    source: int
    target: int
    rule: str
    numerical_changes: dict[str, str] = field(default_factory=dict)


class TerminationDictionaries:
    def __init__(self) -> None:
        self.variables = Dictionary("v", ["kind", "symbol"])
        self.memories = Dictionary("m", ["memory"])
        self.rules = Dictionary("r", ["symbol"])

    def variable(self, kind: str, symbol: str) -> str:
        return self.variables.intern((kind, symbol), [kind, symbol])

    def memory(self, memory: str) -> str:
        return self.memories.intern(memory, [memory])

    def rule(self, symbol: str) -> str:
        return self.rules.intern(symbol, [symbol])

    def tables(self) -> dict[str, Table]:
        named = {"variables": self.variables, "memory": self.memories, "rules": self.rules}
        return {name: table for name, d in named.items() if (table := d.table(name)) is not None}


def _ordered_variables(vertex: TerminationVertex) -> list[tuple[str, str]]:
    values = vertex.values()
    return [(kind, name) for kind in VARIABLE_KINDS for name in values[kind]]


def _cycle_table(edges: list[TerminationEdge]) -> Table:
    if edges:
        vertices = [edges[0].source, *(edge.target for edge in edges)]
        edge_indices = [edge.index for edge in edges]
    else:
        vertices, edge_indices = [], []
    return Table(
        name="cycle",
        columns=["key", "value"],
        rows=[
            ["cycle_vertex_indices", ",".join(map(str, vertices))],
            ["cycle_edge_indices", ",".join(map(str, edge_indices))],
        ],
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
            f"{dicts.variable('numerical', name)}:{change}" for name, change in edge.numerical_changes.items()
        )
        edge_rows.append([edge.index, edge.source, edge.target, dicts.rule(edge.rule), changes])

    return Document(
        header=header,
        sections=[
            _cycle_table(edges),
            Table(name="vertices", columns=["idx", "mem", *aliases], rows=vertex_rows),
            Table(name="edges", columns=["idx", "src", "tgt", "rule", "changes"], rows=edge_rows),
        ],
    )
