# Index Table: solution `failures.*`

One row per selected failure, each pointing into `failures/<id>/`. Universal mode includes at most `n` non-cycle failures and may include one additional cycle.

When all solution-evidence flags are disabled, this instead contains one task-only row for a failed validation: `task_file` is populated and every other column is null. No `failures/<id>/` directory is created.

| Column | Meaning |
|---|---|
| `id` | Stable failure id, e.g. `cycle-001`, also the `failures/<id>/` directory name. |
| `category` | Failure category: `cycle`, `deadend`, or `open_state`. |
| `status` | Native search status that produced the failure, including resource exhaustion. |
| `seed` | Search or rollout seed. |
| `task_file` | Task filename. |
| `origin` | Evidence source, `find_solution`. |
| `witness_trace` | Relative path to the witness-trace file, or empty if none. |
| `witness` | Relative path to the witness file. |
| `successors` | Relative path to the successors file, or empty if none. |
| `plan_trace` | Relative path to the FF plan trace from the open-state witness, or empty if none. |
