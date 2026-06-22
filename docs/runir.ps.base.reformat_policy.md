# runir.ps.base.reformat_policy

Reformats an existing base sketch policy file in place.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `policy_file` | string | required | Path to the sketch policy file to parse and rewrite. |

## Output

Returns a compact success object. No `output_dir` is used.

```json
{
  "tool": "runir.ps.base.reformat_policy",
  "status": "success",
  "primary": {
    "successful": true,
    "policy_file": "<basename>",
    "kind": "sketch"
  },
  "artifacts": {"policy_file": "<basename>"},
  "items": []
}
```

The file at `policy_file` is replaced with RunIR's canonical formatted representation.
