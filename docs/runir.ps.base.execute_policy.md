# runir.ps.base.execute_policy

## Python Call

```python
result = execute_policy(
    task_context,
    policy,
    classifier=None,
    num_rollouts=1,
    random_seed=0,
    random_seed_start=0,
    shuffle_labeled_succ_nodes=True,
    max_arity=0,
    max_num_states=None,
    max_time_seconds=None,
)
```

Dump with `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.MD, DumpFormat.JSON))`.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`; contains its parent `DomainContext`. |
| `policy` | `Policy` | required | Policy candidate returned by `create_policy(...)` or `write_empty_policy(...)`. |
| `classifier` | `Classifier | None` | `None` | Optional unsolvability classifier candidate returned by `create_classifier(...)`. |
| `num_rollouts` | `int` | `1` | Number of rollout seeds to execute. |
| `random_seed` | `int` | `0` | Seed used when `num_rollouts == 1`. |
| `random_seed_start` | `int` | `0` | First seed used when `num_rollouts > 1`. |
| `shuffle_labeled_succ_nodes` | `bool` | `True` | Shuffle successor labels during rollout search. |
| `max_arity` | `int` | `0` | Maximum sketch arity. |
| `max_num_states` | `int | None` | `None` | Per-subgoal state budget. |
| `max_time_seconds` | `float | None` | `None` | Per-subgoal wall-clock budget in seconds. |

## Output / Dump Artifacts
Normalized execution output contains one task entry per rollout seed, representative failures, and trace-only successes. State rows carry feature values plus `fluent`/`derived` facts for witness/cycle states; transition rows carry action labels and matched rule symbols. `hstar` is exact remaining lifted plan length in actions (`inf` = proven dead, empty = budget exhausted); `hlmcut` is the raw LM-cut lower bound. Dictionaries, counterexamples, traces, and successors use the [base sketch-policy output format](output/runir.ps.base.counterexamples.md).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # run metadata: config, command, rollout budgets, hstar budgets (JSON only)
  summary.{psv,md,json}                  # run index/counts table
  failures.{psv,md,json}                 # one row per representative failure (index)
  successes.{psv,md,json}                # one row per successful rollout trace (index)
  dicts/
    features.{psv,md,json}               # run-global dictionary: f0,f1,… -> feature symbol
    rules.{psv,md,json}                  # run-global dictionary: r0,r1,… -> rule symbol
    actions.{psv,md,json}                # run-global dictionary: a0,a1,… -> ground action
    atoms.{psv,md,json}                  # run-global dictionary: p0,p1,… -> ground atom (+ kind)
  failures/
    <id>/                                # one directory per representative failure; <id> already
                                         # encodes the category (e.g. cycle-001, open_state-002)
      meta.json                          # per-failure metadata (see docs/index.md)
      witness.{psv,md,json}              # witness state or cycle
      trace.{psv,md,json}                # path to the witness, present when a path exists
      successors.{psv,md,json}           # 1-step successors of the witness (open_state, cycle, deadend)
  successes/
    <id>/                                # one directory per successful rollout
      meta.json                          # per-success metadata (see docs/index.md)
      trace.{psv,md,json}                # complete successful rollout trace; no witness/successors
```

Everything for one failure is local to `failures/<id>/`; everything for one successful rollout is local to `successes/<id>/`. The run-global alias dictionaries live under
`dicts/`.

## Output Files

The shared [base sketch-policy output format](output/runir.ps.base.counterexamples.md) defines dictionary, witness, trace, successor, section, and flag schemas. Execute-specific details:

- `source` is `find_solution`; `seed` is the rollout seed.
- Successors are emitted in full (never truncated) for `open_state`, `cycle`, and `deadend` witnesses.

`failures` and `successes` indexes are written in requested formats. `summary.*` is the run/counts table; `manifest.json` is JSON-only metadata.

### Failures

`failures.{psv,md,json}`: one row per representative failure, each pointing into `failures/<id>/`.

| Column | Meaning |
|---|---|
| `id` | Stable failure id, e.g. `cycle-001` (also the `failures/<id>/` directory name). |
| `category` | Failure category (`cycle`, `deadend`, `open_state`, `resource_limit`, …). |
| `status` | Execution status that produced the failure (e.g. `CYCLE`). |
| `seed` | Rollout seed. |
| `problem` | Problem file path. |
| `source` | Counterexample source (e.g. `find_solution`). |
| `trace` | Relative path to the trace file, or empty if none. |
| `witness` | Relative path to the witness file. |
| `successors` | Relative path to the successors file, or empty if none. |

```text
id|category|status|seed|problem|source|trace|witness|successors
cycle-001|cycle|CYCLE|0|p01.pddl|find_solution|failures/cycle-001/trace.psv|failures/cycle-001/witness.psv|failures/cycle-001/successors.psv
```


### Successes

`successes.{psv,md,json}`: one row per successful rollout. Success artifacts contain only `successes/<id>/trace.*`; all successful seeds are listed.

| Column | Meaning |
|---|---|
| `id` | Stable success id, e.g. `success-001` (also the `successes/<id>/` directory name). |
| `category` | Always `success`. |
| `status` | Execution status, usually `SUCCESS`. |
| `seed` | Rollout seed. |
| `problem` | Problem file path. |
| `source` | Trace source (e.g. `find_solution`). |
| `trace` | Relative path to the successful trace file. |

```text
id|category|status|seed|problem|source|trace
success-001|success|SUCCESS|0|p01.pddl|find_solution|successes/success-001/trace.psv
```
