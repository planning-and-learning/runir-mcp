# runir.uns.prove_classifier

## Python Call

```python
result = prove_classifier(
    domain_context,
    task_context,
    classifier,
    max_num_states=1_000_000,
    max_time_seconds=1_000_000_000.0,
)
```

Use `dump_result(result, output_dir, formats=(DumpFormat.JSON,))` when filesystem artifacts are
needed. Validation itself is in-memory.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`. |
| `classifier` | `Classifier` | required | Classifier candidate returned by `create_classifier(...)`. |
| `max_num_states` | `int` | `1_000_000` | Reachable-state enumeration budget. |
| `max_time_seconds` | `float` | `1_000_000_000.0` | Enumeration/proof wall-clock budget in seconds. |

## Output / Dump Artifacts
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
