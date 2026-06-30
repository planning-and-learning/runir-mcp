# Dumping

Validation calls return typed Python result objects and do not write files. Dumping is the explicit
boundary for external processes that need JSON, PSV, or Markdown artifacts on disk.

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
)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `result` | `ValidationResult` | required | Result from `execute_policy`, `prove_policy`, `execute_module_program`, `prove_module_program`, or `prove_classifier`. |
| `output_dir` | `str | Path` | required | Directory to create and write into. |
| `formats` | `tuple[DumpFormat, ...]` | `(DumpFormat.JSON,)` | Requested output formats. |

Always writes compact `result.json`. For policy/module-program execute/prove results, requesting
`DumpFormat.PSV`, `DumpFormat.MD`, or `DumpFormat.JSON` also writes the richer witness/trace artifact
tree described by the output-format docs.

Returns `DumpResult`:

| Field | Type | Description |
|---|---|---|
| `output_dir` | `Path` | Absolute output directory. |
| `files` | `tuple[Path, ...]` | Files or rich artifact entry points written by the dump call. |

## `dump_validation_history`

```python
dumped = dump_validation_history(
    history,
    output_dir,
    formats=(DumpFormat.JSON,),
)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `history` | `ValidationHistory` | required | History object managed by the caller. |
| `output_dir` | `str | Path` | required | Directory to create and write into. |
| `formats` | `tuple[DumpFormat, ...]` | `(DumpFormat.JSON,)` | Currently writes `history.json` when `DumpFormat.JSON` is included. |

## Example

```python
result = prove_policy(domain, task, policy)
dump_result(result, "artifacts/prove-policy", formats=(DumpFormat.PSV, DumpFormat.JSON))
```
