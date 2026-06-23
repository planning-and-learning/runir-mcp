# pyrunir-mcp Tool Docs

This directory documents the JSON calling arguments and normalized output structure for each exposed `pyrunir-mcp` tool.

## Tools

- [`runir.ps.base.create_empty_policy`](runir.ps.base.create_empty_policy.md)
- [`runir.ps.base.reformat_policy`](runir.ps.base.reformat_policy.md)
- [`runir.ps.base.execute_policy`](runir.ps.base.execute_policy.md)
- [`runir.ps.base.prove_policy`](runir.ps.base.prove_policy.md)
- [`runir.ps.ext.create_empty_module_program`](runir.ps.ext.create_empty_module_program.md)
- [`runir.ps.ext.reformat_module_program`](runir.ps.ext.reformat_module_program.md)
- [`runir.ps.ext.reformat_module`](runir.ps.ext.reformat_module.md)
- [`runir.ps.ext.execute_module_program`](runir.ps.ext.execute_module_program.md)
- [`runir.ps.ext.prove_module_program`](runir.ps.ext.prove_module_program.md)
- [`runir.ps.ext.prove_termination`](runir.ps.ext.prove_termination.md)
- [`runir.uns.create_empty_classifier`](runir.uns.create_empty_classifier.md)
- [`runir.uns.reformat_classifier`](runir.uns.reformat_classifier.md)
- [`runir.uns.prove_classifier`](runir.uns.prove_classifier.md)

## Shared Conventions

All paths are strings. The caller must pass an `output_dir` for tools that create run artifacts. A tool invocation reserves that directory by writing `.pyrunir-mcp-output` if it is empty; if it already contains prior MCP output, the tool writes to `run-002`, `run-003`, etc. under it.

Normalized successful tool results are JSON objects with at least:

```json
{
  "schema_version": 1,
  "tool": "<tool-name>",
  "status": "success|failure|error",
  "primary": {"successful": true},
  "summary": {},
  "artifacts": {},
  "prompt_summary": {},
  "items": []
}
```

Tool errors return `status: "error"` and `primary.category: "tool_error"`. Parser errors generally surface as tool errors with `primary.error_type`, `primary.message`, and, when available, a source excerpt.

## Output File Formats

Counterexample, trace, and successor output for the base sketch-policy tools (`execute_policy`, `prove_policy`) shares one spec: the [base sketch-policy output format](output/runir.ps.base.counterexamples.md). It defines the PSV/Markdown/JSON renderings, the run-global alias dictionaries (`features`/`rules`/`actions`/`atoms`), the sectioned witness files, and the flag vocabulary. Each tool doc covers only its own index/summary layer and tool-specific options.
