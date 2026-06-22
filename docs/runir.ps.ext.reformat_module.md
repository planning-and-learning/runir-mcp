# runir.ps.ext.reformat_module

Reformats an extended module file in place.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `module_file` | string | required | Path to the module file. |

## Output

Returns a compact success object. No `output_dir` is used.

```json
{
  "tool": "runir.ps.ext.reformat_module",
  "status": "success",
  "primary": {
    "successful": true,
    "module_file": "<basename>",
    "kind": "module"
  },
  "artifacts": {"module_file": "<basename>"},
  "items": []
}
```

The file is replaced with RunIR's canonical formatted representation.
