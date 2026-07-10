# Index Table: execute `failures.*`

One row per representative failure, each pointing into `failures/<id>/`.

| Column | Meaning |
|---|---|
| `id` | Stable failure id, e.g. `cycle-001`, also the `failures/<id>/` directory name. |
| `category` | Failure category, such as `cycle`, `deadend`, `open_state`, or `out_of_states`. |
| `status` | Execution status that produced the failure, e.g. `failure` or `out_of_states`. |
| `seed` | Rollout seed. |
| `task_file` | Task filename. |
| `origin` | Counterexample source, currently `find_solution`. |
| `trace` | Relative path to the trace file, or empty if none. |
| `witness` | Relative path to the witness file. |
| `successors` | Relative path to the successors file, or empty if none. |
| `plan_trace` | Relative path to the FF plan trace file from the open-state witness, or empty if none. |
