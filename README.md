# pyrunir-mcp

MCP server exposing pyrunir tools for planning-and-learning agents.

## Roles

Set `PYRUNIR_MCP_ROLE` before launching the server. The server and invoke CLI fail closed when the role is missing, so restricted agents must be launched with an explicit role:

- `kr/ps/base`: sketch-policy proof, execution, and formatting tools.
- `kr/ps/ext`: module-program proof, structural termination, execution, and formatting tools.
- `kr/uns`: unsolvability classifier proof and formatting tools.
- `all`: every pyrunir MCP tool; use only for trusted, unrestricted local maintenance.

Slash roles also accept dotted aliases such as `kr.ps.base`. The server rejects missing or unknown roles at startup.

## Tool Documentation

Per-tool calling arguments and normalized output structures are documented in [`docs/index.md`](docs/index.md). The individual tool pages cover:

- `runir.ps.base.create_empty_policy`, `runir.ps.base.reformat_policy`, `runir.ps.base.execute_policy`, and `runir.ps.base.prove_sketch_policy`
- `runir.ps.ext.create_empty_module_program`, `runir.ps.ext.reformat_module_program`, `runir.ps.ext.reformat_module`, `runir.ps.ext.execute_module_program`, `runir.ps.ext.prove_module_program`, and `runir.ps.ext.prove_termination`
- `runir.uns.create_empty_classifier`, `runir.uns.reformat_classifier`, and `runir.uns.prove_classifier`

Start with the index for shared result conventions, especially the distinction between counterexample witness files and path trace files.

## Output Contract

Proof and execution tools write layered artifacts under the requested `output_dir`. If that directory already contains output, the tool allocates a numbered child directory such as `run-002` instead of overwriting. Results include `primary` orchestration fields, a structured `summary`, and `items` with relative paths to per-counterexample files and, when available, path trace files. See [`docs/index.md`](docs/index.md) for the exact shared contract and the per-tool pages for argument tables.
