# Section Table: open-state FF plan trace `[facts]`

Used by: [`../runir.ps.open_state.plan_trace.md`](../runir.ps.open_state.plan_trace.md).

Per-state fluent and derived atoms for planning states visited by the FF plan from an open-state witness. Static atoms are interned in `atoms.*` and are not repeated in `[facts]`.

| Column | Meaning |
|---|---|
| `state` | Planning-state id, formatted as `sK`. |
| `atoms` | Comma-separated `pK` aliases for fluent and derived atoms that hold in this state. Aliases come from the run-global `atoms.*` dictionary. |
