# runir.ps.ext.prove_termination

## Python API Status

This page documents the structural-termination output table design.

## Current Status

The artifact layout below defines the structural-termination output format.

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
