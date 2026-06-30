# runir.ps.ext.reformat_module

## Python Call

```python
module_program = create_module_program(domain_context, module_program_file)
```

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `module_program_file` | `str | Path | None` | required for parsing existing program | Module-program file to parse. |

The current public API works at module-program granularity and does not expose a top-level
`reformat_module` function.

## Return / Side Effects

The current public API does not expose standalone module parsing or reformatting. Use `create_module_program(domain_context, module_program_file)` to parse a complete module program into a typed `ModuleProgram`.
