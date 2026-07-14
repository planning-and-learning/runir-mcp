# Index Table: solution `successes.*`

One row per selected successful trace. Success artifacts contain only `successes/<id>/trace.*`.

| Column | Meaning |
|---|---|
| `id` | Stable success id, e.g. `success-001`, also the `successes/<id>/` directory name. |
| `category` | Always `success`. |
| `status` | Native search status, normally `success`. |
| `seed` | Search or rollout seed. |
| `task_file` | Task filename. |
| `origin` | Trace source, `find_solution`. |
| `trace` | Relative path to the successful trace file. |
