# runir.ps.ext.create_empty_module_program

Writes the canonical empty extended module program. This tool performs creation only; use `runir.ps.ext.reformat_module_program` to parse-check and rewrite an existing module program.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `module_program_file` | string | required | Path where the empty module program should be written. |

## Output

Returns the same compact artifact shape as the reformat tool:

```json
{
  "tool": "runir.ps.ext.create_empty_module_program",
  "status": "success",
  "primary": {
    "successful": true,
    "module_program_file": "<basename>",
    "kind": "module-program"
  },
  "artifacts": {"module_program_file": "<basename>"},
  "items": []
}
```

The file at `module_program_file` is overwritten with the canonical empty module program.
