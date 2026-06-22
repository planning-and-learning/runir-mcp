# runir.ps.base.prove_sketch_policy

Proves a base sketch policy on one grounded planning task.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `problem_file` | string | required | Path to one problem PDDL file. |
| `sketch_file` | string | required | Sketch policy file. |
| `output_dir` | string | required | Directory for normalized proof artifacts. |
| `num_threads` | integer | `1` | Grounding/loading worker count. |
| `max_num_states` | integer | `100000` | Proof search state budget. |
| `max_time_seconds` | number | `5.0` | Proof wall-clock budget in seconds. Alias: `max_time`. |

## Output

Uses the shared proof artifact structure with counterexamples for the single requested task.

## Output Directory

```text
output_dir/
  summary.json
  summary.md
  raw/stdout.txt
  raw/stderr.txt
  counterexamples/<category>/<id>.json
  traces/<category>/<id>.json
```
