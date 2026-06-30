# runir.ps.ext.create_empty_module_program

## Python Call

```python
module_program = create_module_program(domain_context, None)
```

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `module_program_file` | `str | Path | None` | `None` | Pass `None` to create the built-in empty module program in memory. |

The current public API does not expose a top-level writer for an empty module-program file.

## Return / Side Effects

`create_module_program(domain_context, None)` returns a `ModuleProgram` with `source == CandidateSource.EMPTY` and does not write files.

There is no current public API function that writes a canonical empty module-program file.
