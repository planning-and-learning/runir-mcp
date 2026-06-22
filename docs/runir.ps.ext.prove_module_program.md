# runir.ps.ext.prove_module_program

Proves an extended module program on one grounded planning task.

## Arguments

| Name | Type | Default | Description |
|---|---:|---:|---|
| `domain_file` | string | required | Path to the planning domain PDDL file. |
| `problem_file` | string | required | Path to one problem PDDL file. |
| `module_program_file` | string | required | Extended module program file. |
| `output_dir` | string | required | Directory for normalized proof artifacts. |
| `num_threads` | integer | `1` | Grounding/loading worker count. |
| `max_num_states` | integer | `100000` | Proof search state budget. |
| `max_time_seconds` | number | `5.0` | Proof wall-clock budget in seconds. |
| `max_arity` | integer | `0` | Maximum module-program arity. |

## Output

Uses the shared proof artifact structure with `tool: "runir.ps.ext.prove_module_program"`. Counterexample states may include module-program metadata such as memory state and module symbol.

## Output Directory

```text
output_dir/
  summary.json
  summary.md
  raw/stdout.txt
  raw/stderr.txt
  counterexamples/<category>/<id>.json
  traces/<category>/<id>.json
```
