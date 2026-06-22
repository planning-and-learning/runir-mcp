# runir.ps.base.execute_policy

Executes a base sketch policy on one grounded planning task. This is the cheap validation stage used before proof.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `problem_file` | string | required | Path to one problem PDDL file. |
| `sketch_file` | string | required | Sketch policy file. |
| `output_dir` | string | required | Directory for normalized output and raw rollout dumps. |
| `num_threads` | integer | `1` | Grounding/loading worker count. |
| `random_seed` | integer | `0` | Seed used when `num_rollouts == 1`. |
| `random_seed_start` | integer | `0` | First seed used when `num_rollouts > 1`. |
| `num_rollouts` | integer | `1` | Number of rollout seeds to execute. |
| `shuffle_labeled_succ_nodes` | boolean | `true` | Shuffle successor labels during rollout search. |
| `max_arity` | integer | `0` | Maximum sketch arity. |
| `max_num_states` | integer or null | `null` | Per-subgoal state budget. |
| `max_time` | number or null | `null` | Per-subgoal wall-clock budget in seconds. |
| `dump_max_steps` | integer or null | `null` | Maximum path transitions dumped. |
| `dump_max_states` | integer or null | `null` | Cap on dumped state objects. |
| `replay_trace` | string or null | `null` | Path to a prior trace to replay/validate. |

## Output

Returns normalized execution output with one task entry per rollout seed and representative failure entries. State objects always include `feature_values`, `fluent_facts`, and `derived_atoms`. Transition objects always include concrete action labels and compact matched rule symbols.

## Output Directory

```text
output_dir/
  summary.md
  manifest.json
  task-001_seed-0_trace.json
  failures/
  counterexamples/<category>/<id>.json
  traces/<category>/<id>.json
```

Counterexample files hold the witness. Trace files, when present, hold only the path to that witness.
