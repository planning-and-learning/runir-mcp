# runir.ps.base.reformat_policy

Reformats an existing base sketch policy file in place.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `sketch_file` | string | required | Path to the sketch policy file to parse and rewrite. |

## Output

Returns a compact success object. No `output_dir` is used.

```json
{
  "tool": "runir.ps.base.reformat_policy",
  "status": "success",
  "primary": {
    "successful": true,
    "sketch_file": "<basename>",
    "kind": "sketch"
  },
  "artifacts": {"sketch_file": "<basename>"},
  "items": []
}
```

The file at `sketch_file` is replaced with Runir's canonical formatted representation.
