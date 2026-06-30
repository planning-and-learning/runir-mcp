# runir.ps.ext.reformat_module_program

## Python Call

```python
module_program = create_module_program(domain_context, module_program_file)
```

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `module_program_file` | `str | Path | None` | required for parsing existing program | Module-program file to parse. Pass `None` to create the empty module program in memory. |

The current public API parses candidates into typed objects. It does not expose a top-level
`reformat_module_program` function for rewriting arbitrary files in place.

## Return / Side Effects

`create_module_program(domain_context, module_program_file)` returns a typed `ModuleProgram` with `source == CandidateSource.FILE` and `source_file` set to the resolved path. It does not rewrite the module-program file.

There is no current public API function that reformats an existing module-program file in place.
