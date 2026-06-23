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
| `max_open_state_counterexamples` | integer | `1` | Maximum number of `open_state` counterexamples to write. |
| `max_deadend_transition_counterexamples` | integer | `1` | Maximum number of `deadend_transition` counterexamples to write. |
| `max_arity` | integer | `0` | Maximum module-program arity. |

## Output

Counterexample output is bounded by category: at most `max_open_state_counterexamples` open states, at most `max_deadend_transition_counterexamples` deadend transitions, and exactly one cycle counterexample if a cycle exists. Cycle witnesses are not counted against the open/deadend bounds.

The dictionaries, counterexamples, traces, and successors use the shared [module-program output format](output/runir.ps.ext.counterexamples.md) with `tool: "runir.ps.ext.prove_module_program"`; `summary.{psv,md,json}` indexes them and `manifest.json` holds run metadata (JSON-only). Failure categories are `open_state`, `deadend_transition`, and `cycle`. Like `prove_policy`, proof has no rollout seeds (no `@seed`); otherwise each witness produces the same counterexample / trace (the path to the witness, present when one exists) / successors files.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                        # run metadata: config, budgets (JSON only)
  summary.{psv,md,json}                # run index/counts table
  features.{psv,md,json}               # run-global dictionary: f0,f1,… -> feature symbol
  rules.{psv,md,json}                  # run-global dictionary: r0,r1,… -> module rule (+ src/tgt memory)
  actions.{psv,md,json}                # run-global dictionary: a0,a1,… -> ground action
  atoms.{psv,md,json}                  # run-global dictionary: p0,p1,… -> ground atom (+ kind)
  memory.{psv,md,json}                 # run-global dictionary: m0,m1,… -> (module, memory-state)
  counterexamples/<category>/<id>.{psv,md,json}  # witness vertex or cycle
  traces/<category>/<id>.{psv,md,json}           # path to witness, present when a path exists
  successors/<category>/<id>.{psv,md,json}       # 1-step successors of the witness
```
