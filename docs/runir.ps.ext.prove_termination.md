# runir.ps.ext.prove_termination

## Python API Status

This page documents the structural-termination output layout. Table schemas are in [module-program termination tables](tables/runir.ps.ext.prove_termination.md).

## Python API

```python
prove_termination(
    domain_context,
    module_program,
    *,
    max_features=10,
    use_incomplete_preprocessing=True,
)
```

`max_features` caps the relevant boolean and numerical features in each residual memory
component. `use_incomplete_preprocessing` enables the sound incomplete pass before the complete
structural-termination check.

Each module result exposes `scc_results`: `None` means incomplete preprocessing proved
termination before complete SIEVE ran, while an empty list means complete SIEVE ran without a
residual SCC. Nonempty entries contain the Boolean and numerical features projected into each SCC.

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
      witness.{psv,md,json}              # non-termination cycle, when enabled
```

Passing `include_witness=False` to `dump_result(...)` skips witness construction but keeps each counterexample row with `witness_path: null`; `run.json` records `evidence.termination_witness`.
