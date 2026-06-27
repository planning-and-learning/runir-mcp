"""Build the per-mistake unsolvability-classifier witness.

Each mistake is one atomic witness state, written as its own `failures/<id>/witness` document (a
`[state]` + `[facts]` doc, like the policy tools). See docs/output/runir.uns.prove_classifier.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import Flag, WitnessState, counterexample_document
from pyrunir_mcp.tables import Document


@dataclass(frozen=True)
class ClassifierRow:
    id: str
    category: str  # false_positive | false_negative
    state: int
    features: dict[str, JsonValue] = field(default_factory=dict)
    fluent: tuple[str, ...] = ()


def classifier_witness(row: ClassifierRow, feature_symbols: list[str], dicts: Dictionaries, header: list[tuple[str, str]]) -> Document:
    """The single misclassified state as a `[state]` + `[facts]` witness document (boolean features)."""
    state = WitnessState(state=row.state, features=row.features, fluent=row.fluent, flags=(Flag.WITNESS,))
    return counterexample_document(
        header=header,
        feature_symbols=feature_symbols,
        states=[state],
        transitions=[],
        cycle=None,
        dicts=dicts,
        ext=False,
        include_hstar=False,
        include_hlmcut=False,
    )
