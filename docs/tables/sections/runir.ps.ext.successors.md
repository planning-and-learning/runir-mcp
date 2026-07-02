# Section Table: module-program `[successors]`

Used by: [`../runir.ps.ext.counterexamples.md`](../runir.ps.ext.counterexamples.md).

Off-graph one-step successor frontier from module-program source control locations along a trace or cycle.

| Column | Meaning |
|---|---|
| `source_state` | Source planning-state id (`sK`). |
| `source_module` | Source module alias (`MK`). |
| `source_memory` | Source memory-location alias (`mK`). |
| `action` | Ground-action alias (`aK`) from [`actions.*`](../dictionaries/runir.ps.ext.actions.md). |
| `target_state` | Target planning-state id (`sK`). |
| `target_module` | Resulting module alias (`MK`) for a selected move; blank for a gap. |
| `target_memory` | Resulting memory-location alias (`mK`) for a selected move; blank for a gap. |
| `rule` | Module-rule alias (`rK`) selecting the move, or empty when no rule selects it. |
| `flags` | Flags for the target state, such as `GOAL` or `DEADEND`. |
| `delta` | Space-separated changed features as `fK:before>after`, using aliases from [`features.*`](../dictionaries/runir.ps.ext.features.md). |

Generated successors are off-graph, so both source and target are represented as planning state plus control location. For a gap, `rule`, `target_module`, and `target_memory` are blank.
