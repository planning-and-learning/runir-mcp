# pyrunir-mcp

MCP server exposing pyrunir tools for planning-and-learning agents.

## Roles

Set `PYRUNIR_MCP_ROLE` before launching the server. The server and invoke CLI fail closed when the role is missing, so restricted agents must be launched with an explicit role:

- `kr/ps/base`: sketch-policy proof, execution, and formatting tools.
- `kr/ps/ext`: module-program proof, structural termination, execution, and formatting tools.
- `kr/uns`: unsolvability classifier proof and formatting tools.
- `all`: every pyrunir MCP tool; use only for trusted, unrestricted local maintenance.

Slash roles also accept dotted aliases such as `kr.ps.base`. The server rejects missing or unknown roles at startup.

## Output Contract

Proof and execution tools write layered artifacts under the requested `output_dir`. If that directory already contains output, the tool allocates a numbered child directory such as `run-002` instead of overwriting. Results include `primary` orchestration fields, a structured `summary`, and `items` with relative paths to per-counterexample or per-trace files.
