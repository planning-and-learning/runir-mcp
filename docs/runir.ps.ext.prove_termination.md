# runir.ps.ext.prove_termination

## Python API Status

This page documents the structural-termination output layout. Table schemas are in [module-program termination tables](tables/runir.ps.ext.prove_termination.md).

## Current Status

The artifact layout below defines the structural-termination output format.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  run.json                               # run envelope: metadata and artifact paths (JSON only)
  summary.{psv,md,json}                  # run index table
  dicts/
    variables.{psv,md,json}              # dictionary: v0,v1,… -> (kind, variable symbol)
    memory.{psv,md,json}                 # dictionary: m0,m1,… -> memory state
    rules.{psv,md,json}                  # dictionary: r0,r1,… -> module rule
  failures/
    <id>/                                # <id> = structural_termination-001, …
      witness.{psv,md,json}              # non-termination cycle
```
