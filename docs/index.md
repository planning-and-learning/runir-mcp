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

### On-disk layout

Every run-artifact tool writes the same local, grouped tree: run-global alias dictionaries under
`dicts/`, and everything for one failure local to `failures/<id>/`.

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json            # execute: run metadata (JSON only). prove tools return the MCP envelope.
  summary.{psv,md,json}    # run index/counts table
  failures.{psv,md,json}   # one row per representative failure (index into failures/<id>/)
  dicts/
    <name>.{psv,md,json}   # run-global dictionaries (features, rules, actions, atoms, … per tool family)
  failures/
    <id>/                  # <id> already encodes the category (cycle-001, open_state-002, false_positive-001, …)
      meta.json            # per-failure metadata (below)
      witness.{psv,md,json}      # the witness state(s) / cycle
      trace.{psv,md,json}        # path to the witness, when one exists
      successors.{psv,md,json}   # 1-step successors of the witness, when applicable
```

`meta.json` (one per failure) carries the same fields as the matching `failures.psv` row plus the
relative artifact filenames present:

```json
{
  "id": "cycle-001",
  "category": "cycle",
  "status": "CYCLE",
  "seed": 0,
  "problem": "p01.pddl",
  "source": "find_ground_solution",
  "files": {"witness": "witness.psv", "trace": "trace.psv", "successors": "successors.psv"}
}
```

A tool that has no trace/successors for a failure simply omits those files (and their `files` keys).

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

Witness, trace, and successor output is shared per tool family. Each spec defines the PSV/Markdown/JSON renderings, the run-global alias dictionaries (under `dicts/`), the sectioned witness files (under `failures/<id>/`), and the flag vocabulary; each tool doc covers only its own index/summary layer and tool-specific options.

- Base sketch-policy tools (`execute_policy`, `prove_policy`): [base output format](output/runir.ps.base.counterexamples.md).
- Module-program tools (`execute_module_program`, `prove_module_program`): [module-program output format](output/runir.ps.ext.counterexamples.md) — mirrors base plus the `(module, memory-state)` control dimension.
- Termination (`prove_termination`): [termination output format](output/runir.ps.ext.prove_termination.md) — a different witness shape (a cycle in the structural termination graph); same PSV encoding.
- Unsolvability classifier (`prove_classifier`): [classifier output format](output/runir.uns.prove_classifier.md) — one `failures/<id>/witness` per misclassified state (boolean feature valuations), indexed by `failures.{psv,md,json}`; no traces or successors.
