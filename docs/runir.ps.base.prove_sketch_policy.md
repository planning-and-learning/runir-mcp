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
| `max_time_seconds` | number | `5.0` | Proof wall-clock budget in seconds. |
| `max_open_state_counterexamples` | integer | `1` | Maximum number of `open_state` counterexamples to write. |
| `max_deadend_transition_counterexamples` | integer | `1` | Maximum number of `deadend_transition` counterexamples to write. |

## Output

Counterexample output is bounded by category: at most `max_open_state_counterexamples` open states, at most `max_deadend_transition_counterexamples` deadend transitions, and exactly one cycle counterexample if a cycle exists. Cycle witnesses are not counted against the open/deadend bounds.

Uses the shared proof artifact structure with counterexamples for the single requested task.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  summary.json
  summary.md
  raw/stdout.txt
  raw/stderr.txt
  counterexamples/<category>/<id>.json
  traces/<category>/<id>.json
```
