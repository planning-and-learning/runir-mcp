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
`dump_result(...)` currently writes the compact `result.json` sidecar for classifier proof results.
It records the validation kind/status, task context ID/index, classifier candidate metadata, the
typed observation payload, and aggregate classifier proof counts.

The richer classifier witness layout documented in
[unsolvability-classifier output format](output/runir.uns.prove_classifier.md) is retained as the
historical output-format reference, but it is not emitted by the current public
`dump_result(...)` path.

Categories:

- `false_positive`: classifier predicts unsolvable on a solvable state.
- `false_negative`: classifier predicts solvable on an unsolvable/dead-end state.

## Output Directory

```text
output_dir/
  result.json                            # compact validation result sidecar
```
