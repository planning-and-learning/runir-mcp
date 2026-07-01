# Section Table: module-program `[state]`

Used by: [`../runir.ps.ext.counterexamples.md`](../runir.ps.ext.counterexamples.md).

Single witness control state for non-cycle module-program counterexamples.

| Column | Meaning |
|---|---|
| `state` | Planning-state id (`sK`). |
| `module` | Module alias (`MK`) from [`modules.*`](../dictionaries/runir.ps.ext.modules.md). |
| `memory` | Memory-location alias (`mK`) from [`memory.*`](../dictionaries/runir.ps.ext.memory.md). |
| `flags` | Comma-separated state flags; see [base flag values](runir.ps.base.flags.md). |
| `hstar` | Shortest remaining plan length for `state`; `inf` for proven deadends; empty when inconclusive. |
| `hlmcut` | LM-cut lower bound for `state`. |
| `f0`, `f1`, ... | Feature values, one column per row in [`features.*`](../dictionaries/runir.ps.ext.features.md). |
