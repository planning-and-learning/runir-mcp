# Section Table: module-program `[facts]`

Used by: [`../runir.ps.ext.counterexamples.md`](../runir.ps.ext.counterexamples.md).

Per-planning-state fluent and derived facts. Facts are keyed by planning state, not vertex, because several vertices may share the same planning state.

| Column | Meaning |
|---|---|
| `state` | Planning-state id (`sK`). |
| `atoms` | Comma-separated atom aliases (`pK`) from [`atoms.*`](../dictionaries/runir.ps.ext.atoms.md). |

Static atoms are interned in `atoms.*` and are not repeated in `[facts]`.
