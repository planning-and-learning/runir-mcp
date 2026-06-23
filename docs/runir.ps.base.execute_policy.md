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

## Output

Returns normalized execution output with one task entry per rollout seed and representative failure entries. State rows always carry feature values and (for witness/cycle states) `fluent`/`derived` facts. Transition rows always carry concrete action labels and the matched rule symbol. The on-disk encoding of the dictionaries, counterexamples, traces, and successors is the shared [base sketch-policy output format](output/runir.ps.base.counterexamples.md).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                        # run metadata: config, command, budgets (JSON only)
  summary.{psv,md,json}                # run index/counts table
  features.{psv,md,json}               # run-global dictionary: f0,f1,… -> feature symbol
  rules.{psv,md,json}                  # run-global dictionary: r0,r1,… -> rule symbol
  actions.{psv,md,json}                # run-global dictionary: a0,a1,… -> ground action
  atoms.{psv,md,json}                  # run-global dictionary: p0,p1,… -> ground atom (+ kind)
  failures.{psv,md,json}               # one row per representative failure (index)
  counterexamples/<category>/<id>.{psv,md,json}  # witness state or cycle
  traces/<category>/<id>.{psv,md,json}           # path to witness, present when a path exists
  successors/<category>/<id>.{psv,md,json}       # 1-step successors of the witness (open_state, cycle, deadend)
```

## Output Files

The alias dictionaries (`features`/`rules`/`actions`/`atoms`) and the `counterexamples`/`traces`/`successors` files use the shared [base sketch-policy output format](output/runir.ps.base.counterexamples.md) — PSV/Markdown/JSON renderings, alias dictionaries, sectioned witness files, the section reference, and the flag vocabulary. This tool's specifics:

- `source` is `find_ground_solution`; `seed` is the rollout seed.
- Successors are emitted in full (never truncated) for `open_state`, `cycle`, and `deadend` witnesses.

It also writes the `failures` index below (execute-specific). Each artifact is written in all three formats (`.psv`, `.md`, `.json`) during experimentation, controlled by a `formats` option that later narrows to `["psv"]`. `summary.{psv,md,json}` is the run index/counts table; `manifest.json` holds run metadata (config, command, budgets) and stays JSON-only per the project output policy.

### Failures

Files `failures.psv` / `failures.md` / `failures.json` — one row per representative failure (the first failure seen per task/category). Replaces the former `failures/<category>/<id>.json` tree.

| Column | Meaning |
|---|---|
| `id` | Stable failure id, e.g. `cycle-001`. |
| `category` | Failure category (`cycle`, `deadend`, `open_state`, `resource_limit`, …). |
| `status` | Execution status that produced the failure (e.g. `CYCLE`). |
| `seed` | Rollout seed. |
| `problem` | Problem file path. |
| `source` | Counterexample source (e.g. `find_ground_solution`). |
| `trace` | Relative path to the trace file, or empty if none. |
| `counterexample` | Relative path to the counterexample file. |
| `successors` | Relative path to the successors file, or empty if none. |

```text
id|category|status|seed|problem|source|trace|counterexample|successors
cycle-001|cycle|CYCLE|0|p01.pddl|find_ground_solution|traces/cycle/cycle-001.psv|counterexamples/cycle/cycle-001.psv|successors/cycle/cycle-001.psv
```
