# runir.ps.ext.prove_termination

## Python API Status

There is no top-level Python `prove_termination` entry point in the current public API. This page is retained only as the structural-termination output-format reference from the old tool surface.

## Current Status

No current public Python function runs structural termination proof. The artifact layout below is retained as historical output-format reference only.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # run metadata: config (JSON only)
  summary.{psv,md,json}                  # run index/counts table
  dicts/
    variables.{psv,md,json}              # dictionary: v0,v1,… -> (kind, variable symbol)
    memory.{psv,md,json}                 # dictionary: m0,m1,… -> memory state
    rules.{psv,md,json}                  # dictionary: r0,r1,… -> module rule
  failures/
    <id>/                                # <id> = structural_termination-001, …
      meta.json                          # per-failure metadata (see docs/index.md)
      witness.{psv,md,json}              # non-termination cycle
```
