# Index Table: execute `summary.*`

Used by execute-policy and execute-module-program runs.

| Column | Meaning |
|---|---|
| `id` | Stable representative failure id, e.g. `cycle-001`. |
| `category` | Failure category, such as `cycle`, `deadend`, `open_state`, or `resource_limit`. |
| `status` | Execution status that produced the representative failure. |
| `seed` | Rollout seed. |
| `problem` | Problem file path/name. |
