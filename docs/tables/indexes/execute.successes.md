# Index Table: execute `successes.*`

One row per successful rollout. Success artifacts contain only `successes/<id>/trace.*`; all successful seeds are listed.

| Column | Meaning |
|---|---|
| `id` | Stable success id, e.g. `success-001`, also the `successes/<id>/` directory name. |
| `category` | Always `success`. |
| `status` | Execution status, usually `success`. |
| `seed` | Rollout seed. |
| `task_file` | Task filename. |
| `origin` | Trace source, currently `find_solution`. |
| `trace` | Relative path to the successful trace file. |
