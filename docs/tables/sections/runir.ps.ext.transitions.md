# Section Table: module-program `[transitions]`

Used by: [`../runir.ps.ext.counterexamples.md`](../runir.ps.ext.counterexamples.md).

Edges in witness traces or cycles between module-program control states.

| Column | Meaning |
|---|---|
| `step` | Transition index within the witness trace or cycle. |
| `source_state_id` | Source planning-state id (`sK`). |
| `source_module_id` | Source module alias (`MK`). |
| `source_memory_id` | Source memory-location alias (`mK`). |
| `target_state_id` | Target planning-state id (`sK`). |
| `target_module_id` | Target module alias (`MK`). |
| `target_memory_id` | Target memory-location alias (`mK`). |
| `rule_id` | Module-rule alias (`rK`) from [`rules.*`](../dictionaries/runir.ps.ext.rules.md). |
| `action_id` | Ground-action alias (`aK`) from [`actions.*`](../dictionaries/runir.ps.ext.actions.md). |
| `deltas` | Space-separated changed features as `fK:before>after`, using aliases from [`features.*`](../dictionaries/runir.ps.ext.features.md). |
