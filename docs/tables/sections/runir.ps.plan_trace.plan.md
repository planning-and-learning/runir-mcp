# Section Table: open-state FF plan trace `[plan]`

Used by: [`../runir.ps.open_state.plan_trace.md`](../runir.ps.open_state.plan_trace.md).

Each row is one FF-selected task action from the open-state witness toward a goal. The rows are planner evidence only; they do not imply that the policy or module program selected the action.

| Column | Meaning |
|---|---|
| `step` | Zero-based FF plan step. |
| `source` | Planning-state id before the action, formatted as `sK`. |
| `action` | Action alias from the run-global `actions.*` dictionary. |
| `target` | Planning-state id after the action, formatted as `sK`. |
| `delta` | Space-separated changed features as `fK:before>after`, using aliases from the run-global `features.*` dictionary. |
