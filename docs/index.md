# pyrunir-mcp Tool Docs

This directory documents the JSON calling arguments and normalized output structure for each exposed `pyrunir-mcp` tool.

## Tools

- [`runir.ps.base.create_empty_policy`](runir.ps.base.create_empty_policy.md)
- [`runir.ps.base.reformat_policy`](runir.ps.base.reformat_policy.md)
- [`runir.ps.base.execute_policy`](runir.ps.base.execute_policy.md)
- [`runir.ps.base.prove_sketch_policy`](runir.ps.base.prove_sketch_policy.md)
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

All paths are strings. The caller must pass an `output_dir` for tools that create run artifacts. A tool invocation reserves that directory if it is empty; if it already contains prior MCP output, the tool writes to `run-002`, `run-003`, etc. under it.

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

## Counterexample And Trace Contract

Proof and execute tools write three kinds of files:

- `summary.json` / `summary.md`: compact index and counts.
- `counterexamples/<category>/<id>.json`: the counterexample witness.
- `traces/<category>/<id>.json`: a path trace, present only when a real path exists.

Counterexample files use this rule:

- open/deadend state witnesses contain a single `state` object;
- cycle witnesses contain the circular trace segment under `cycle`, `states`, and `transitions`;
- structural witnesses, such as termination graphs, stay in the counterexample file and do not create a trace file.

Trace files use this rule:

- traces contain a path to the counterexample state, or a path to a state in the cycle;
- `trace_available` means a real path trace exists, not merely that state evidence exists;
- no trace file is written for unordered witness-state evidence.

State evidence always contains `feature_values`, `fluent_facts`, and `derived_atoms`. Static atoms are intentionally omitted because they are repeated in every state and recoverable from domain/problem files.
