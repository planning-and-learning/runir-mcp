# Section Table: base `[successors]`

Used by: [`../runir.ps.base.counterexamples.md`](../runir.ps.base.counterexamples.md).

One-step successor frontier from states along a trace or cycle.

| Column | Meaning |
|---|---|
| `source` | Source planning-state id (`sK`). |
| `action` | Ground-action alias (`aK`) from [`actions.*`](../dictionaries/runir.ps.base.actions.md). |
| `target` | Target planning-state id (`sK`). |
| `rule` | Sketch-rule alias (`rK`) selecting the move, or empty when no rule selects it. |
| `flags` | Flags for the target state, such as `GOAL` or `DEADEND`. |
| `delta` | Space-separated changed features as `fK:before>after`, using aliases from [`features.*`](../dictionaries/runir.ps.base.features.md). |

A progressing move with an empty `rule` cell is the missing guidance signal.
