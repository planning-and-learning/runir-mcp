# runir.uns.create_empty_classifier

Writes the canonical empty unsolvability classifier. This tool performs creation only; use `runir.uns.reformat_classifier` to parse-check and rewrite an existing classifier.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `classifier_file` | string | required | Path where the empty classifier should be written. |

## Output

Returns the same compact artifact shape as the reformat tool:

```json
{
  "tool": "runir.uns.create_empty_classifier",
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

The file at `classifier_file` is overwritten with the canonical empty classifier.
