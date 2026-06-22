# runir.uns.reformat_classifier

Reformats an existing unsolvability classifier file in place.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `classifier_file` | string | required | Path to the classifier file to parse and rewrite. |

## Output

Returns a compact success object. No `output_dir` is used.

```json
{
  "tool": "runir.uns.reformat_classifier",
  "status": "success",
  "primary": {
    "successful": true,
    "classifier_file": "<basename>",
    "num_features": 0
  },
  "artifacts": {"classifier_file": "<basename>"},
  "items": []
}
```
