# Index Table: execute `failures.*`

One row per representative failure, each pointing into `failures/<id>/`.

| Column | Meaning |
|---|---|
| `id` | Stable failure id, e.g. `cycle-001`, also the `failures/<id>/` directory name. |
| `category` | Failure category, such as `cycle`, `deadend`, `open_state`, or `resource_limit`. |
| `status` | Execution status that produced the failure, e.g. `CYCLE`. |
| `seed` | Rollout seed. |
| `problem` | Problem file path/name. |
| `source` | Counterexample source, currently `find_solution`. |
| `trace` | Relative path to the trace file, or empty if none. |
| `witness` | Relative path to the witness file. |
| `successors` | Relative path to the successors file, or empty if none. |
| `plan_trace` | Relative path to the FF plan trace file from the open-state witness, or empty if none. |
