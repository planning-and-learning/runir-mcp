# runir.ps.ext.execute_module_program

Executes an extended module program on one grounded planning task. This is the cheap validation stage used before proof.

## Arguments

Same as `runir.ps.base.execute_policy`, except the policy path argument is:

| Name | Type | Default | Description |
|---|---:|---:|---|
| `module_program_file` | string | required | Extended module program file. |

All other execution arguments are identical: `domain_file`, `problem_file`, `output_dir`, rollout settings, resource settings including `max_time_seconds`, and dump settings.

## Output

Same normalized structure as `runir.ps.base.execute_policy`, with `tool: "runir.ps.ext.execute_module_program"`. The dictionaries, counterexamples, traces, and successors use the shared [module-program output format](output/runir.ps.ext.counterexamples.md) (vertices carry their `(module, memory-state)` location).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                        # run metadata: config, command, budgets (JSON only)
  summary.{psv,md,json}                # run index/counts table
  features.{psv,md,json}               # run-global dictionary: f0,f1,… -> feature symbol
  rules.{psv,md,json}                  # run-global dictionary: r0,r1,… -> module rule (+ src/tgt memory)
  actions.{psv,md,json}                # run-global dictionary: a0,a1,… -> ground action
  atoms.{psv,md,json}                  # run-global dictionary: p0,p1,… -> ground atom (+ kind)
  memory.{psv,md,json}                 # run-global dictionary: m0,m1,… -> (module, memory-state)
  failures.{psv,md,json}               # one row per representative failure (index)
  counterexamples/<category>/<id>.{psv,md,json}  # witness vertex or cycle
  traces/<category>/<id>.{psv,md,json}           # path to witness, present when a path exists
  successors/<category>/<id>.{psv,md,json}       # 1-step successors of the witness (open_state, cycle, deadend)
```

## Output Files

The dictionaries (`features`/`rules`/`actions`/`atoms`/`memory`) and the `counterexamples`/`traces`/`successors` files use the shared [module-program output format](output/runir.ps.ext.counterexamples.md). This tool's specifics:

- `source` is `find_ground_solution`; `seed` is the rollout seed.
- Successors are emitted for `open_state`, `cycle`, and `deadend` witnesses, capped by `dump_max_successors`.

It also writes the `failures` index (one row per representative failure), identical in shape to `execute_policy`'s. Each artifact is written in all three formats during experimentation; `summary.{psv,md,json}` is the run index and `manifest.json` holds run metadata (JSON-only).
