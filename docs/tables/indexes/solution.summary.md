# Index Table: solution `summary.*`

Used by base-policy and module-program `find_solution(...)` runs.

When all solution-evidence flags are disabled, a failed validation has one task-only row: `task_file` is populated and every other column is null.

| Column | Meaning |
|---|---|
| `id` | Stable evidence id, e.g. `cycle-001` or `success-001`. |
| `category` | Evidence category: `success`, `cycle`, `deadend`, or `open_state`. |
| `status` | Native search status that produced the evidence, including resource exhaustion. |
| `seed` | Search or rollout seed. |
| `task_file` | Task filename. |
