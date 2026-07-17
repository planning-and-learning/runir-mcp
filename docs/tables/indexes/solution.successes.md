# Index Table: solution `successes.*`

One row per selected successful witness trace. Success artifacts contain only `successes/<id>/witness_trace.*`.

| Column | Meaning |
|---|---|
| `id` | Stable success id, e.g. `success-001`, also the `successes/<id>/` directory name. |
| `category` | Always `success`. |
| `status` | Native search status, normally `success`. |
| `seed` | Search or rollout seed. |
| `task_file` | Task filename. |
| `origin` | Witness-trace source, `find_solution`. |
| `witness_trace` | Relative path to the successful witness-trace file. |
