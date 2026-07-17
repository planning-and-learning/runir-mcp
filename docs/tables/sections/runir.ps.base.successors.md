# Section Table: base `[successors]`

Used by: [`../runir.ps.base.counterexamples.md`](../runir.ps.base.counterexamples.md).

One-step successor frontier from states along a witness trace or cycle.

| Column | Meaning |
|---|---|
| `source_state_id` | Source planning-state id (`sK`). |
| `action_id` | Ground-action alias (`aK`) from [`actions.*`](../dictionaries/runir.ps.base.actions.md). |
| `target_state_id` | Target planning-state id (`sK`). |
| `rule_id` | Sketch-rule alias (`rK`) selecting the move, or empty when no rule selects it. |
| `flags` | Flags for the target state, such as `goal` or `deadend`. |
| `deltas` | Space-separated changed features as `fK:before>after`, using aliases from [`features.*`](../dictionaries/runir.ps.base.features.md). |

A progressing move with an empty `rule_id` cell is the missing guidance signal.
