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
| `max_time_seconds` | number or null | `null` | Per-subgoal wall-clock budget in seconds. |
| `dump_max_steps` | integer or null | `null` | Maximum path transitions dumped. |
| `dump_max_states` | integer or null | `null` | Cap on dumped state objects. |

## Output

Returns normalized execution output with one task entry per rollout seed and representative failure entries. State objects always include `feature_values`, `fluent_facts`, and `derived_atoms`. Transition objects always include concrete action labels and compact matched rule symbols.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  summary.md
  manifest.json
  failures/<category>/<id>.json       # lightweight index to the normalized witness
  counterexamples/<category>/<id>.json # witness state or cycle
  traces/<category>/<id>.json          # path to witness, present when a path exists
```

Counterexample files hold the witness state or cycle. Trace files, when present, hold only the path to that witness. Failure files are lightweight indices and do not duplicate states or transitions.
