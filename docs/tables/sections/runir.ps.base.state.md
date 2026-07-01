# Section Table: base `[state]`

Used by: [`../runir.ps.base.counterexamples.md`](../runir.ps.base.counterexamples.md).

Single witness state for non-cycle base policy counterexamples.

| Column | Meaning |
|---|---|
| `id` | Planning-state id (`sK`). |
| `flags` | Comma-separated state flags; see [base flag values](runir.ps.base.flags.md). |
| `hstar` | Shortest remaining plan length; `inf` for proven deadends; empty when inconclusive. |
| `hlmcut` | LM-cut lower bound for the same planning state. |
| `f0`, `f1`, ... | Feature values, one column per row in [`features.*`](../dictionaries/runir.ps.base.features.md). |
