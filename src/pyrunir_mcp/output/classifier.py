"""Build the per-mistake unsolvability-classifier witness.

Each mistake is one atomic witness state, written as its own `failures/<id>/witness` document (a
`[states]` + `[facts]` document for classifier witness output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyrunir_mcp.enums import Flag, RunItemCategory
from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import WitnessState, counterexample_document
from pyrunir_mcp.tables import Document


def _json_dict() -> dict[str, JsonValue]:
    return {}


@dataclass(frozen=True)
class ClassifierRow:
    id: str
    category: RunItemCategory
    state: int
    features: dict[str, JsonValue] = field(default_factory=_json_dict)
    fluent: tuple[str, ...] = ()
    derived: tuple[str, ...] = ()


def classifier_witness(
    row: ClassifierRow,
    feature_symbols: list[str],
    dicts: Dictionaries,
    header: list[tuple[str, str]],
) -> Document:
    """The single misclassified state as a `[states]` + `[facts]` witness document (boolean features)."""
    state = WitnessState(
        state=row.state,
        features=row.features,
        fluent=row.fluent,
        derived=row.derived,
        flags=(Flag.WITNESS,),
    )
    return counterexample_document(
        header=header,
        feature_symbols=feature_symbols,
        states=[state],
        transitions=[],
        cycle=False,
        dicts=dicts,
        ext=False,
        include_hstar=False,
        include_hlmcut=False,
    )
