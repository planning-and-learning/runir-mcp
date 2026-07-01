# Section Table: open-state FF plan trace `[states]`

Used by: [`../runir.ps.open_state.plan_trace.md`](../runir.ps.open_state.plan_trace.md).

Planning states visited by the FF plan from an open-state witness. These are task-level states, not policy/module-program control states.

| Column | Meaning |
|---|---|
| `state` | Planning-state id, formatted as `sK`. |
| `flags` | State markers. The first row is usually `OPEN`; the last row is usually `GOAL`; empty means no notable marker. |
| `hstar` | Shortest remaining plan length from this state, `inf` for proven deadends, or empty when inconclusive. |
| `hlmcut` | LM-cut lower bound for this state, or empty when unavailable. |
| `f0`, `f1`, ... | Feature values using aliases from the run-global `features.*` dictionary. |
