# Section Table: module-program `[successors]`

Used by: [`../runir.ps.ext.counterexamples.md`](../runir.ps.ext.counterexamples.md).

Off-graph one-step successor frontier from module-program source control locations along a witness trace or cycle.

| Column | Meaning |
|---|---|
| `source_state_id` | Source planning-state id (`sK`). |
| `source_module_id` | Source module alias (`MK`). |
| `source_memory_id` | Source memory-location alias (`mK`). |
| `action_id` | Ground-action alias (`aK`) from [`actions.*`](../dictionaries/runir.ps.ext.actions.md). |
| `target_state_id` | Target planning-state id (`sK`). |
| `target_module_id` | Resulting module alias (`MK`) for a selected move; blank for a gap. |
| `target_memory_id` | Resulting memory-location alias (`mK`) for a selected move; blank for a gap. |
| `rule_id` | Module-rule alias (`rK`) selecting the move, or empty when no rule selects it. |
| `flags` | Flags for the target state, such as `goal` or `deadend`. |
| `deltas` | Space-separated changed features as `fK:before>after`, using aliases from [`features.*`](../dictionaries/runir.ps.ext.features.md). |

Generated successors are off-graph, so both source and target are represented as planning state plus control location. For a gap, `rule_id`, `target_module_id`, and `target_memory_id` are blank.
