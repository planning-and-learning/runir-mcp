# Dumping

Validation is in-memory. Dump only when external processes need JSON, PSV, or Markdown files.

## `DumpFormat`

| Value | Meaning |
|---|---|
| `DumpFormat.JSON` | Machine-readable JSON. |
| `DumpFormat.PSV` | Pipe-separated LLM-readable artifacts. |
| `DumpFormat.MD` | Human-readable Markdown artifacts. |

## `dump_result`

```python
dumped = dump_result(
    result,
    output_dir,
    formats=(DumpFormat.JSON,),
    include_witness_trace=True,
    include_plan_trace=True,
    include_successors=True,
)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `result` | `ValidationResult` | required | Result from `find_solution`, `prove_classifier`, or a termination proof. |
| `output_dir` | `str | Path` | required | Directory to create and write into. |
| `formats` | `tuple[DumpFormat, ...]` | `(DumpFormat.JSON,)` | Requested output formats. |
| `include_witness_trace` | `bool` | `True` | Emit failure-path and successful witness traces. |
| `include_plan_trace` | `bool` | `True` | Run FF and emit plan traces for open-state witnesses. |
| `include_successors` | `bool` | `True` | Expand and emit one-step successor frontiers. |

Always writes compact machine metadata and mandatory failure witnesses. The three evidence flags apply only to policy/module-program solution results and independently prevent both construction and output of the disabled evidence. Disabling witness traces omits failure `witness_trace.*` files and all successful witness-trace entries. Disabling plan traces avoids the separate FF search. Disabling successors avoids frontier-expander construction and successor generation.

For reported open-state failures, enabled plan-trace generation uses `result.plan_trace_budget`, not `result.search_budget`. The default is 1,000,000 states and 10 seconds.

| Field | Type | Description |
|---|---|---|
| `output_dir` | `Path` | Absolute output directory. |
| `files` | `tuple[Path, ...]` | Files or rich artifact entry points written by the dump call. |

Rich `run.json` envelopes and base/ext solution `manifest.json` files use schema version 2. Solution manifests contain an `evidence` object with the three booleans `witness_trace`, `plan_trace`, and `successors`; nullable artifact paths therefore distinguish disabled evidence from evidence that was enabled but unavailable.

## `dump_validation_history`

```python
dumped = dump_validation_history(history, output_dir, formats=(DumpFormat.JSON,))
```

| Name | Type | Default | Description |
|---|---|---|---|
| `history` | `ValidationHistory` | required | Caller-owned history object. |
| `output_dir` | `str | Path` | required | Directory to create and write into. |
| `formats` | `tuple[DumpFormat, ...]` | `(DumpFormat.JSON,)` | Writes `history.json` when JSON is included. |

```python
result = find_solution(task, policy, universal=True)
dump_result(result, "artifacts/find-solution", formats=(DumpFormat.PSV, DumpFormat.JSON))
```
