# runir.uns.prove_classifier

## Python Call

```python
result = prove_classifier(
    task_context,
    classifier,
    search_budget=SearchBudget(max_num_states=1_000_000, max_time_seconds=None),
)
```

Dump with `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.JSON))`.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`; contains its parent `DomainContext`. |
| `classifier` | `Classifier` | required | Classifier candidate returned by `create_classifier(...)`. |
| `search_budget` | `SearchBudget` | `SearchBudget(max_num_states=1_000_000, max_time_seconds=None)` | Reachable-state enumeration/proof budget; `None` leaves that side unconstrained. |
| `max_mistakes_per_category` | `int` | `5` | Maximum representative false-positive and false-negative witness states retained for rich artifacts. Aggregate counts still cover the full checked graph. |

## Output / Dump Artifacts

`result.json` is always written and contains validation kind/status, task context ID/index, classifier metadata, typed observation payload, aggregate counts, and the search budget.

When classifier mistakes are found, `dump_result(...)` also writes rich counterexample artifacts using the [unsolvability-classifier table schema](tables/runir.uns.prove_classifier.md). Representative mistakes are written under `failures/<id>/`; counts in `result.json` remain aggregate counts for the full checked graph.

Categories:

- `false_positive`: classifier predicts unsolvable on a solvable state.
- `false_negative`: classifier predicts solvable on an unsolvable/dead-end state.

## Output Directory

```text
output_dir/
  result.json                            # compact validation result sidecar
  run.json                               # rich artifact envelope, when mistakes are emitted
  summary.{psv,md,json}                  # representative mistake index
  dicts/
    features.{psv,md,json}               # f0,f1,... -> classifier feature symbol, when non-empty
    atoms.{psv,md,json}                  # p0,p1,... -> atom text/kind
  failures/
    false_negative-001/
      witness.{psv,md,json}              # [state] + [facts]
      meta.json
```
