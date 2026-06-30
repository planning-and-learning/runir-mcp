# runir.uns.create_empty_classifier

## Python Call

```python
classifier = create_classifier(domain_context, None)
```

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `classifier_file` | `str | Path | None` | `None` | Pass `None` to create an empty classifier in memory. |

The current public API does not expose a top-level writer for an empty classifier file.

## Return / Side Effects

`create_classifier(domain_context, None)` returns a `Classifier` with `source == CandidateSource.EMPTY` and does not write files.

There is no current public API function that writes a canonical empty classifier file.
