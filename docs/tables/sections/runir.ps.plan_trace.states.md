# Section Table: open-state FF plan trace `[states]`

Used by: [`../runir.ps.open_state.plan_trace.md`](../runir.ps.open_state.plan_trace.md).

Planning states visited by the FF plan from an open-state witness. These are task-level states, not policy/module-program control states. Their atoms are interned in the run-global `atoms.*` dictionary, including static atoms; per-state fluent and derived atoms are listed in [`[facts]`](runir.ps.plan_trace.facts.md).

| Column | Meaning |
|---|---|
| `state_id` | Planning-state id, formatted as `sK`. |
| `flags` | State markers. The first row is usually `open`; the last row is usually `goal`; empty means no notable marker. |
| `hstar` | Shortest remaining plan length from this state, `inf` for proven deadends, or empty when inconclusive. |
| `hlmcut` | LM-cut lower bound for this state, or empty when unavailable. |
| `f0`, `f1`, ... | Feature values using aliases from the run-global `features.*` dictionary. |
