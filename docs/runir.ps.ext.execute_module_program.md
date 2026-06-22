# runir.ps.ext.execute_module_program

Executes an extended module program on one grounded planning task. This is the cheap validation stage used before proof.

## Arguments

Same as `runir.ps.base.execute_policy`, except the policy path argument is:

| Name | Type | Default | Description |
|---|---:|---:|---|
| `module_program_file` | string | required | Extended module program file. |

All other execution arguments are identical: `domain_file`, `problem_file`, `output_dir`, rollout settings, resource settings including `max_time_seconds`, and dump settings.

## Output

Same normalized structure as `runir.ps.base.execute_policy`, with `tool: "runir.ps.ext.execute_module_program"`. Raw trace objects also include module-program metadata such as memory state/module fields.

## Output Directory

```text
output_dir/
  summary.md
  manifest.json
  trace_seed-<seed>.json
  failures/<category>/<id>.json
  counterexamples/<category>/<id>.json
  traces/<category>/<id>.json
```

Counterexample files hold the witness. Trace files, when present, hold only the path to that witness.
