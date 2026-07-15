# Candidates

Candidates are typed in-memory wrappers around parsed Runir objects. They replace repeatedly passing
candidate file paths to each validation tool.

## Sources

Every candidate has:

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Stable per-domain ID such as `policy_000001`. |
| `value` | Runir object | Parsed policy/module-program/classifier object. |
| `source` | `CandidateSource` | `CandidateSource.FILE` or `CandidateSource.EMPTY`. |
| `source_file` | `Path | None` | Absolute source path when created from a file. |

The wrapper is an immutable domain-level snapshot. Task validation materializes its canonical typed
value once in the task's matching Runir repository and reuses that value internally; it never rereads
`source_file`. Results retain the original wrapper passed by the caller.

## `create_policy`

```python
policy = create_policy(domain_context, policy_file)
empty_policy = create_policy(domain_context, None)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Context returned by `create_domain_context(...)`. |
| `policy_file` | `str | Path | None` | required | Base sketch policy file. Pass `None` for an empty policy. |

Returns `Policy`.

## `write_empty_policy`

```python
policy = write_empty_policy(domain_context, policy_file)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Context returned by `create_domain_context(...)`. |
| `policy_file` | `str | Path` | required | Destination for Runir's canonical empty policy text. |

Returns the same `Policy` object shape as `create_policy(domain_context, None)`, with `source_file`
set to the written path.

## `create_module_program`

```python
module_program = create_module_program(domain_context, module_program_file)
empty_program = create_module_program(domain_context, None)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Context returned by `create_domain_context(...)`. |
| `module_program_file` | `str | Path | None` | required | Extended module-program file. Pass `None` for the built-in empty module program. |

Returns `ModuleProgram`.

## `create_classifier`

```python
classifier = create_classifier(domain_context, classifier_file)
empty_classifier = create_classifier(domain_context, None)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Context returned by `create_domain_context(...)`. |
| `classifier_file` | `str | Path | None` | required | Unsolvability classifier file. Pass `None` for an empty classifier. |

Returns `Classifier`.
