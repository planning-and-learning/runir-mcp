# Section Table: module-program `[states]`

Used by: [`../runir.ps.ext.counterexamples.md`](../runir.ps.ext.counterexamples.md).

Control-state annotations and feature vectors for module-program witnesses, traces, and cycles. A non-cycle witness contains one row; cycle witnesses repeat the first row as the final row to close the cycle.

| Column | Meaning |
|---|---|
| `state_id` | Planning-state id (`sK`). |
| `module_id` | Module alias (`MK`) from [`modules.*`](../dictionaries/runir.ps.ext.modules.md). |
| `memory_id` | Memory-location alias (`mK`) from [`memory.*`](../dictionaries/runir.ps.ext.memory.md). |
| `flags` | Comma-separated state flags; see [base flag values](runir.ps.base.flags.md). |
| `hstar` | Shortest remaining plan length for `state_id`; `inf` for proven deadends; empty when inconclusive. |
| `hlmcut` | LM-cut lower bound for `state_id`. |
| `f0`, `f1`, ... | Feature values, one column per row in [`features.*`](../dictionaries/runir.ps.ext.features.md). |
