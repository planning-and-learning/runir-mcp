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
  .pyrunir-mcp-output
  summary.md
  manifest.json
  failures/<category>/<id>.json       # lightweight index to the normalized witness
  counterexamples/<category>/<id>.json # witness state or cycle
  traces/<category>/<id>.json          # path to witness, present when a path exists
```

Counterexample files hold the witness state or cycle. Trace files, when present, hold only the path to that witness. Failure files are lightweight indices and do not duplicate states or transitions.
