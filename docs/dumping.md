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
| `result` | `ValidationResult` | required | Result from `execute_policy`, `prove_policy`, `execute_module_program`, `prove_module_program`, or `prove_classifier`. |
| `output_dir` | `str | Path` | required | Directory to create and write into. |
| `formats` | `tuple[DumpFormat, ...]` | `(DumpFormat.JSON,)` | Requested output formats. |

Always writes compact `result.json`. Policy/module-program execute/prove results also write requested witness/trace artifacts.

| Field | Type | Description |
|---|---|---|
| `output_dir` | `Path` | Absolute output directory. |
| `files` | `tuple[Path, ...]` | Files or rich artifact entry points written by the dump call. |

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
result = prove_policy(task, policy)
dump_result(result, "artifacts/prove-policy", formats=(DumpFormat.PSV, DumpFormat.JSON))
```
