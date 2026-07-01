# runir.ps.base.reformat_policy

## Python Calls

```python
policy = create_policy(domain_context, policy_file)
```

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `policy_file` | `str | Path | None` | required for parsing existing policy | Policy file to parse. Pass `None` to create the empty policy in memory. |

The current public API parses candidates into typed objects. It does not expose a top-level
`reformat_policy` function for rewriting arbitrary policy files in place.

## Return / Side Effects

`create_policy(domain_context, policy_file)` returns a typed `Policy` with `source == CandidateSource.FILE` and `source_file` set to the resolved path. It does not rewrite the policy file.

This page documents the policy formatting workflow and expected formatted policy behavior.
