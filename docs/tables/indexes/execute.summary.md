# Index Table: execute `summary.*`

Used by execute-policy and execute-module-program runs.

| Column | Meaning |
|---|---|
| `id` | Stable representative failure id, e.g. `cycle-001`. |
| `category` | Failure category, such as `cycle`, `deadend`, `open_state`, or `out_of_states`. |
| `status` | Execution status that produced the representative failure. |
| `seed` | Rollout seed. |
| `task_file` | Task filename. |
