# runir.uns.prove_classifier

Proves an unsolvability classifier against full reachable-state-space ground truth for one problem.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `problem_file` | string | required | Path to one problem PDDL file. |
| `output_dir` | string | required | Directory for normalized proof artifacts. |
| `classifier_file` | string | required | Classifier file to prove. Required — there is no implicit empty-classifier fallback. |
| `max_num_states` | integer | `1000000` | Reachable-state enumeration budget. |
| `max_time_seconds` | number | `1000000000.0` | Enumeration/proof wall-clock budget. |
| `max_false_positive_counterexamples` | integer | `20` | Maximum number of `false_positive` counterexamples to record. |
| `max_false_negative_counterexamples` | integer | `20` | Maximum number of `false_negative` counterexamples to record. |

## Output

Classifier mistakes are single **witness states**, not path traces — there are no `trace` or `successors` files, only a `witness`. Each mistake is one `failures/<id>/` directory (`meta.json` + `witness`), indexed by `failures.{psv,md,json}`. The dictionaries (under `dicts/`) and the witness files use the [unsolvability-classifier output format](output/runir.uns.prove_classifier.md); `summary.{psv,md,json}` carries run counts and `manifest.json` holds run metadata (JSON-only).

Categories:

- `false_positive`: classifier predicts unsolvable on a solvable state.
- `false_negative`: classifier predicts solvable on an unsolvable/dead-end state.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # run metadata: config (JSON only)
  summary.{psv,md,json}                  # run index/counts table
  failures.{psv,md,json}                 # one row per classifier mistake (index)
  dicts/
    features.{psv,md,json}               # run-global dictionary: f0,f1,… -> feature symbol
    atoms.{psv,md,json}                  # run-global dictionary: p0,p1,… -> ground atom (+ kind)
  failures/
    <id>/                                # <id> = false_positive-001, false_negative-001, …
      meta.json                          # per-failure metadata (see docs/index.md)
      witness.{psv,md,json}              # the single misclassified state (feature valuations + facts)
```
