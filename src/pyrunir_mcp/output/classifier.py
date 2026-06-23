"""Build the merged unsolvability-classifier counterexamples table.

Each mistake is one atomic witness state, so the whole result is one flat table (one row per
misclassified state). See docs/output/runir.uns.prove_classifier.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.tables import Table


@dataclass(frozen=True)
class ClassifierRow:
    id: str
    category: str  # false_positive | false_negative
    state: int
    features: dict[str, JsonValue] = field(default_factory=dict)
    fluent: tuple[str, ...] = ()


def counterexamples_table(rows: list[ClassifierRow], feature_symbols: list[str], dicts: Dictionaries) -> Table:
    for symbol in feature_symbols:
        dicts.feature(symbol)
    aliases = [f"f{index}" for index in range(len(feature_symbols))]
    columns = ["id", "category", "state", *aliases, "atoms"]
    table_rows: list[list[JsonValue]] = []
    for row in rows:
        values = [row.features.get(symbol) for symbol in feature_symbols]
        atoms = ",".join(dicts.atom("fluent", atom) for atom in row.fluent)
        table_rows.append([row.id, row.category, row.state, *values, atoms])
    return Table(name="counterexamples", columns=columns, rows=table_rows)
