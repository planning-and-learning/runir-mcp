# Section Table: base `[transitions]`

Used by: [`../runir.ps.base.counterexamples.md`](../runir.ps.base.counterexamples.md).

Trace or cycle edges between base planning states.

| Column | Meaning |
|---|---|
| `step` | Transition index within the trace or cycle. |
| `source` | Source planning-state id (`sK`). |
| `target` | Target planning-state id (`sK`). |
| `rule` | Sketch-rule alias (`rK`) from [`rules.*`](../dictionaries/runir.ps.base.rules.md). |
| `action` | Ground-action alias (`aK`) from [`actions.*`](../dictionaries/runir.ps.base.actions.md). |
| `delta` | Space-separated changed features as `fK:before>after`. |
