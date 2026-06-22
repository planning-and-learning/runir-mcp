# runir.ps.base.create_empty_policy

Writes the canonical empty base sketch policy. This tool performs creation only; use `runir.ps.base.reformat_policy` to parse-check and rewrite an existing policy.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `policy_file` | string | required | Path where the empty sketch policy should be written. |

## Output

Returns the same compact artifact shape as the reformat tool:

```json
{
  "tool": "runir.ps.base.create_empty_policy",
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

The file at `policy_file` is overwritten with RunIR's canonical empty sketch representation.
