# runir.ps.base.execute_policy

## Python Call

```python
result = execute_policy(
    domain_context,
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

Use `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.MD, DumpFormat.JSON))`
when filesystem artifacts are needed. Validation itself is in-memory.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`. |
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
Returns normalized execution output with one task entry per rollout seed, representative failure entries, and trace-only entries for every rollout that succeeds. `hstar` values in witness, trace, and successor state rows are computed by converting each reported state into the lifted task and running A* guided by LM-cut; the value is shortest remaining plan length in number of actions, not action cost. `inf` means the state is proven dead; an empty cell means the h* computation exhausted its internal time or state budget before proving a value. The `hlmcut` column reports the raw LM-cut heuristic value for the same lifted state as an admissible lower bound, including when exact `hstar` is too costly. State rows always carry feature values and (for witness/cycle states) `fluent`/`derived` facts. Transition rows always carry concrete action labels and the matched rule symbol. The on-disk encoding of the dictionaries, counterexamples, traces, and successors is the shared [base sketch-policy output format](output/runir.ps.base.counterexamples.md).

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

The alias dictionaries under `dicts/` (`features`/`rules`/`actions`/`atoms`) and the per-failure `witness`/`trace`/`successors` files use the shared [base sketch-policy output format](output/runir.ps.base.counterexamples.md) — PSV/Markdown/JSON renderings, alias dictionaries, sectioned witness files, the section reference, and the flag vocabulary. This tool's specifics:

- `source` is `find_solution`; `seed` is the rollout seed.
- Successors are emitted in full (never truncated) for `open_state`, `cycle`, and `deadend` witnesses.

It also writes the `failures` and `successes` indexes below (execute-specific). Artifacts are written in the formats requested via `dump_result(..., formats=...)`. `summary.{psv,md,json}` is the run index/counts table; `manifest.json` holds run metadata (config, command, budgets) and stays JSON-only per the project output policy.

### Failures

Files `failures.psv` / `failures.md` / `failures.json` — one row per representative failure (the first failure seen per task/category), each pointing into its `failures/<id>/` directory.

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

Files `successes.psv` / `successes.md` / `successes.json` — one row per rollout seed that succeeds. Unlike failures, a success has no witness state and no successor frontier: its artifact is only the complete trace under `successes/<id>/trace.{psv,md,json}`. All successful rollouts from the requested seeds are listed, not just one representative.

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
