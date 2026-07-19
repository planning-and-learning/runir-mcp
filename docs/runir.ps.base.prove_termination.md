# runir.ps.base.prove_termination

## Python API

```python
prove_termination(
    domain_context,
    policy,
    *,
    max_features=10,
    use_incomplete_preprocessing=True,
)
```

`max_features` caps the relevant Boolean and numerical features in the residual policy component. `use_incomplete_preprocessing` enables the sound incomplete pass before the complete structural-termination check. On failure, the witness contains only the first directed cycle found in the residual graph.

The result and its observation report `incomplete_termination_status` as `proved`, `insufficient`, or `disabled`. A nonterminating result retains Runir's typed counterexample graph. The native result exposes `scc_results`: `None` means incomplete preprocessing proved termination before complete SIEVE ran, while an empty list means complete SIEVE ran without a residual SCC.

Table schemas are in [base-policy termination tables](tables/runir.ps.base.prove_termination.md).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  run.json                               # run envelope and artifact paths
  summary.{psv,md,json}                  # run index table
  dicts/
    variables.{psv,md,json}              # v0,v1,... -> (kind, feature symbol)
    rules.{psv,md,json}                  # r0,r1,... -> policy rule
  failures/
    structural_termination-001/
      witness.{psv,md,json}              # nontermination cycle, when enabled
```

Base-policy witnesses intentionally have no memory dictionary or `memory_id` column.
Passing `include_witness=False` to `dump_result(...)` skips witness construction but keeps the counterexample row with `witness_path: null`; `run.json` records `evidence.termination_witness`.
