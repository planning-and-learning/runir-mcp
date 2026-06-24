# runir.ps.ext.prove_termination

Checks structural termination of an extended module program.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `module_program_file` | string | required | Extended module program file. |
| `output_dir` | string | required | Directory for normalized termination artifacts. |

## Output

A non-termination witness is a **cycle in the structural termination graph** — abstract vertices (a memory state plus concept/boolean/numerical variable valuations) connected by module-rule edges. It is reported, not a planning trace: the dictionaries (under `dicts/`) and the per-failure witness (under `failures/<id>/`) use the [module-program termination output format](output/runir.ps.ext.prove_termination.md). A termination witness has no trace or successors. On success no failures are written; the normalized result still carries `program_status` and `nonterminating_modules`.

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
