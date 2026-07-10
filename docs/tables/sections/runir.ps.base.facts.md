# Section Table: base `[facts]`

Used by: [`../runir.ps.base.counterexamples.md`](../runir.ps.base.counterexamples.md).

Per-state fluent and derived facts.

| Column | Meaning |
|---|---|
| `state_id` | Planning-state id (`sK`). |
| `atom_ids` | Comma-separated atom aliases (`pK`) from [`atoms.*`](../dictionaries/runir.ps.base.atoms.md). |

Static atoms are interned in `atoms.*` and are not repeated in `[facts]`.
