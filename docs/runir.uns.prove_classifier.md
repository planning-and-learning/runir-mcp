# runir.uns.prove_classifier

## Python Call

```python
result = prove_classifier(
    task_context,
    classifier,
    max_num_states=1_000_000,
    max_time_seconds=1_000_000_000.0,
)
```

Dump with `dump_result(result, output_dir, formats=(DumpFormat.JSON,))`.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`; contains its parent `DomainContext`. |
| `classifier` | `Classifier` | required | Classifier candidate returned by `create_classifier(...)`. |
| `max_num_states` | `int` | `1_000_000` | Reachable-state enumeration budget. |
| `max_time_seconds` | `float` | `1_000_000_000.0` | Enumeration/proof wall-clock budget in seconds. |

## Output / Dump Artifacts
`dump_result(...)` writes `result.json`: validation kind/status, task context ID/index, classifier metadata, typed observation payload, and aggregate counts. Classifier witness tables: [unsolvability-classifier output format](output/runir.uns.prove_classifier.md).

Categories:

- `false_positive`: classifier predicts unsolvable on a solvable state.
- `false_negative`: classifier predicts solvable on an unsolvable/dead-end state.

## Output Directory

```text
output_dir/
  result.json                            # compact validation result sidecar
```
