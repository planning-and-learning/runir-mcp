# runir.ps.base.execute_policy

Executes a base sketch policy on one grounded planning task. This is the cheap validation stage used before proof.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `problem_file` | string | required | Path to one problem PDDL file. |
| `sketch_file` | string | required | Sketch policy file. |
| `output_dir` | string | required | Directory for the normalized run output. |
| `num_threads` | integer | `1` | Grounding/loading worker count. |
| `random_seed` | integer | `0` | Seed used when `num_rollouts == 1`. |
| `random_seed_start` | integer | `0` | First seed used when `num_rollouts > 1`. |
| `num_rollouts` | integer | `1` | Number of rollout seeds to execute. |
| `shuffle_labeled_succ_nodes` | boolean | `true` | Shuffle successor labels during rollout search. |
| `max_arity` | integer | `0` | Maximum sketch arity. |
| `max_num_states` | integer or null | `null` | Per-subgoal state budget. |
| `max_time_seconds` | number or null | `null` | Per-subgoal wall-clock budget in seconds. |
| `hstar_max_num_states` | integer | `100000` | Per-state A*+LM-cut state budget for computing `hstar`. |
| `hstar_max_time_seconds` | number | `3.0` | Per-state A*+LM-cut wall-clock budget for computing `hstar`. |

## Output

Returns normalized execution output with one task entry per rollout seed and representative failure entries. `hstar` values in witness, trace, and successor state rows are computed by converting each reported state into the lifted task and running A* guided by LM-cut; the value is shortest remaining plan length in number of actions, not action cost. `inf` means the state is proven dead; an empty cell means the h* computation exhausted `hstar_max_time_seconds` or `hstar_max_num_states` before proving a value. The `hlmcut` column reports the raw LM-cut heuristic value for the same lifted state as an admissible lower bound, including when exact `hstar` is too costly. State rows always carry feature values and (for witness/cycle states) `fluent`/`derived` facts. Transition rows always carry concrete action labels and the matched rule symbol. The on-disk encoding of the dictionaries, counterexamples, traces, and successors is the shared [base sketch-policy output format](output/runir.ps.base.counterexamples.md).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # run metadata: config, command, rollout budgets, hstar budgets (JSON only)
  summary.{psv,md,json}                  # run index/counts table
  failures.{psv,md,json}                 # one row per representative failure (index)
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
```

Everything for one failure is local to `failures/<id>/`; the run-global alias dictionaries live under
`dicts/`.

## Output Files

The alias dictionaries under `dicts/` (`features`/`rules`/`actions`/`atoms`) and the per-failure `witness`/`trace`/`successors` files use the shared [base sketch-policy output format](output/runir.ps.base.counterexamples.md) — PSV/Markdown/JSON renderings, alias dictionaries, sectioned witness files, the section reference, and the flag vocabulary. This tool's specifics:

- `source` is `find_solution`; `seed` is the rollout seed.
- Successors are emitted in full (never truncated) for `open_state`, `cycle`, and `deadend` witnesses.

It also writes the `failures` index below (execute-specific). Each artifact is written in all three formats (`.psv`, `.md`, `.json`) during experimentation, controlled by a `formats` option that later narrows to `["psv"]`. `summary.{psv,md,json}` is the run index/counts table; `manifest.json` holds run metadata (config, command, budgets) and stays JSON-only per the project output policy.

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
