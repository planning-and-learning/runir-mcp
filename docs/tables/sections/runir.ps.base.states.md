# Section Table: base `[states]`

Used by: [`../runir.ps.base.counterexamples.md`](../runir.ps.base.counterexamples.md).

State annotations and feature vectors for witnesses, traces, cycles, and successor-frontier targets. A non-cycle witness contains one row; cycle witnesses repeat the first row as the final row to close the cycle.

| Column | Meaning |
|---|---|
| `state_id` | Planning-state id (`sK`). |
| `flags` | Comma-separated state flags; see [base flag values](runir.ps.base.flags.md). |
| `hstar` | Shortest remaining plan length; `inf` for proven deadends; empty when inconclusive. |
| `hlmcut` | LM-cut lower bound for the same planning state. |
| `f0`, `f1`, ... | Feature values, one column per row in [`features.*`](../dictionaries/runir.ps.base.features.md). |
