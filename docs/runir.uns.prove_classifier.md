# runir.uns.prove_classifier

Proves an unsolvability classifier against full reachable-state-space ground truth for one problem.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `problem_file` | string | required | Path to one problem PDDL file. |
| `output_dir` | string | required | Directory for normalized proof artifacts. |
| `classifier_file` | string or null | `null` | Classifier file. Null means empty/default classifier where supported. |
| `max_num_states` | integer | `1000000` | Reachable-state enumeration budget. |
| `max_time_seconds` | number | `1000000000.0` | Enumeration/proof wall-clock budget. |

## Output

Uses the shared proof artifact structure. Classifier mistakes are state witnesses, not path traces, so counterexamples normally have no `trace_path`.

Categories:

- `false_positive`: classifier predicts unsolvable on a solvable state.
- `false_negative`: classifier predicts solvable on an unsolvable/dead-end state.

## Output Directory

```text
output_dir/
  summary.json
  summary.md
  raw/stdout.txt
  raw/stderr.txt
  counterexamples/false_positive/<id>.json
  counterexamples/false_negative/<id>.json
```
