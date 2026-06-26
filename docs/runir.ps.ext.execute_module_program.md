# runir.ps.ext.execute_module_program

Executes an extended module program on one grounded planning task. This is the cheap validation stage used before proof.

## Arguments

Same as `runir.ps.base.execute_policy`, except the policy path argument is:

| Name | Type | Default | Description |
|---|---:|---:|---|
| `module_program_file` | string | required | Extended module program file. |

All other execution arguments are identical: `domain_file`, `problem_file`, `output_dir`, rollout settings, resource settings including `max_time_seconds`, h* settings (`hstar_max_num_states` default `100000`, `hstar_max_time_seconds` default `3.0`), and dump settings.

## Output

Same normalized structure as `runir.ps.base.execute_policy`, with `tool: "runir.ps.ext.execute_module_program"`. `hstar` has the same semantics as base: shortest remaining lifted plan length in number of actions, `inf` for proven deadends, and empty when the per-state A*+LM-cut timeout/state budget is exhausted. The dictionaries (under `dicts/`) and the per-failure witness, trace, and successors files (under `failures/<id>/`) use the shared [module-program output format](output/runir.ps.ext.counterexamples.md) (vertices carry their `(module, memory-state)` location).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # run metadata: config, command, rollout budgets, hstar budgets (JSON only)
  summary.{psv,md,json}                  # run index/counts table
  failures.{psv,md,json}                 # one row per representative failure (index)
  dicts/
    features.{psv,md,json}               # run-global dictionary: f0,f1,… -> feature symbol
    rules.{psv,md,json}                  # run-global dictionary: r0,r1,… -> module rule (+ src/tgt memory)
    actions.{psv,md,json}                # run-global dictionary: a0,a1,… -> ground action
    atoms.{psv,md,json}                  # run-global dictionary: p0,p1,… -> ground atom (+ kind)
    memory.{psv,md,json}                 # run-global dictionary: m0,m1,… -> (module, memory-state)
  failures/
    <id>/                                # <id> already encodes the category (e.g. open_state-001, cycle-001)
      meta.json                          # per-failure metadata (see docs/index.md)
      witness.{psv,md,json}              # witness vertex or cycle
      trace.{psv,md,json}                # path to the witness, present when a path exists
      successors.{psv,md,json}           # 1-step successors of the witness (open_state, cycle, deadend)
```

## Output Files

The dictionaries under `dicts/` (`features`/`rules`/`actions`/`atoms`/`memory`) and the per-failure `witness`/`trace`/`successors` files use the shared [module-program output format](output/runir.ps.ext.counterexamples.md). This tool's specifics:

- `source` is `find_solution`; `seed` is the rollout seed.
- Successors are emitted in full (never truncated) for `open_state`, `cycle`, and `deadend` witnesses.

It also writes the `failures` index (one row per representative failure), identical in shape to `execute_policy`'s. Each artifact is written in all three formats during experimentation; `summary.{psv,md,json}` is the run index and `manifest.json` holds run metadata (JSON-only).
