# Section Table: base `[transitions]`

Used by: [`../runir.ps.base.counterexamples.md`](../runir.ps.base.counterexamples.md).

Edges in witness traces or cycles between base planning states.

| Column | Meaning |
|---|---|
| `step` | Transition index within the witness trace or cycle. |
| `source_state_id` | Source planning-state id (`sK`). |
| `target_state_id` | Target planning-state id (`sK`). |
| `rule_id` | Sketch-rule alias (`rK`) from [`rules.*`](../dictionaries/runir.ps.base.rules.md). |
| `action_id` | Ground-action alias (`aK`) from [`actions.*`](../dictionaries/runir.ps.base.actions.md). |
| `deltas` | Space-separated changed features as `fK:before>after`, using aliases from [`features.*`](../dictionaries/runir.ps.base.features.md). |
