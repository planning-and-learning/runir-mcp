# runir.ps.base.create_empty_policy

## Python Calls

```python
policy = create_policy(domain_context, None)
policy = write_empty_policy(domain_context, policy_file)
```

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `policy_file` | `str | Path` | required for `write_empty_policy` | Destination for Runir's canonical empty policy text. |

`create_policy(domain_context, None)` creates the empty policy in memory and does not write files.
`write_empty_policy(...)` creates the same empty policy and writes the canonical text to `policy_file`.

## Return / Side Effects

`create_policy(domain_context, None)` returns a `Policy` with `source == CandidateSource.EMPTY` and does not write files.

`write_empty_policy(domain_context, policy_file)` returns a `Policy` with `source == CandidateSource.EMPTY`, sets `source_file` to the written path, creates parent directories as needed, and writes Runir's canonical empty sketch text to `policy_file`.
