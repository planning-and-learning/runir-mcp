# runir.uns.reformat_classifier

## Python Call

```python
classifier = create_classifier(domain_context, classifier_file)
```

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `classifier_file` | `str | Path | None` | required for parsing existing classifier | Classifier file to parse. Pass `None` to create the empty classifier in memory. |

The current public API parses classifiers into typed objects. It does not expose a top-level
`reformat_classifier` function for rewriting arbitrary files in place.

## Return / Side Effects

`create_classifier(domain_context, classifier_file)` returns a typed `Classifier` with `source == CandidateSource.FILE` and `source_file` set to the resolved path. It does not rewrite the classifier file.

There is no current public API function that reformats an existing classifier file in place.
