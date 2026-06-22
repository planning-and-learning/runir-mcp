# runir.ps.ext.reformat_module_program

Reformats an extended module-program file in place.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `module_program_file` | string | required | Path to the module-program file. |

## Output

Returns a compact success object. No `output_dir` is used.

```json
{
  "tool": "runir.ps.ext.reformat_module_program",
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

The file is replaced with Runir's canonical formatted representation.
