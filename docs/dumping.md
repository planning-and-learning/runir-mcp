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
dumped = dump_result(result, output_dir, formats=(DumpFormat.JSON,))
```

| Name | Type | Default | Description |
|---|---|---|---|
| `result` | `ValidationResult` | required | Result from `find_solution`, `prove_classifier`, or a termination proof. |
| `output_dir` | `str | Path` | required | Directory to create and write into. |
| `formats` | `tuple[DumpFormat, ...]` | `(DumpFormat.JSON,)` | Requested output formats. |

Always writes compact machine metadata. Policy/module-program solution results use `manifest.json` and also write requested witness/trace artifacts. For reported open-state failures, `dump_result(...)` may write `plan_trace.*` when FF finds a plan from the witness state; this uses `result.plan_trace_budget`, not `result.search_budget`.

| Field | Type | Description |
|---|---|---|
| `output_dir` | `Path` | Absolute output directory. |
| `files` | `tuple[Path, ...]` | Files or rich artifact entry points written by the dump call. |

For base/ext solution results, `manifest.json` records both `search_budget` and `plan_trace_budget`. The default plan-trace budget is 1,000,000 states and 10 seconds.

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
