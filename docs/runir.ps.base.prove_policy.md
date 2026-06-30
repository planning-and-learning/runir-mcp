# runir.ps.base.prove_policy

## Python Call

```python
result = prove_policy(
    domain_context,
    task_context,
    policy,
    classifier=None,
    max_num_states=100_000,
    max_time_seconds=5.0,
)
```

Use `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.MD, DumpFormat.JSON))`
when filesystem artifacts are needed. Validation itself is in-memory.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`. |
| `policy` | `Policy` | required | Policy candidate returned by `create_policy(...)` or `write_empty_policy(...)`. |
| `classifier` | `Classifier | None` | `None` | Optional unsolvability classifier candidate returned by `create_classifier(...)`. |
| `max_num_states` | `int` | `100_000` | Proof search state budget. |
| `max_time_seconds` | `float` | `5.0` | Proof wall-clock budget in seconds. |

## Output / Dump Artifacts
`hstar` values in witness, trace, and successor state rows are computed by converting each reported state into the lifted task and running A* guided by LM-cut. The value is shortest remaining plan length in number of actions, not action cost. `inf` means the state is proven dead; an empty cell means the h* computation exhausted its internal time or state budget before proving a value. The `hlmcut` column reports the raw LM-cut heuristic value for the same lifted state as an admissible lower bound, including when exact `hstar` is too costly.

Counterexample output is bounded by category: at most `max_open_state_counterexamples` open states, at most `max_deadend_transition_counterexamples` deadend transitions, and exactly one cycle counterexample if a cycle exists. Cycle witnesses are not counted against the open/deadend bounds.

The dictionaries (under `dicts/`) and the per-failure witness, trace, and successors files (under `failures/<id>/`) use the shared [base sketch-policy output format](output/runir.ps.base.counterexamples.md); `summary.{psv,md,json}` indexes them for the single requested task and `manifest.json` holds run metadata (JSON-only). Failure categories are `open_state`, `deadend_transition`, and `cycle`. Unlike `execute_policy`, proof has no rollout seeds, so witness headers carry no `@seed`; otherwise each failure produces the same `failures/<id>/` directory (`meta.json` + `witness` + `trace` when a path exists + `successors`).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # run metadata: config, proof budgets, hstar budgets (JSON only)
  summary.{psv,md,json}                  # run index/counts table
  dicts/
    features.{psv,md,json}               # run-global dictionary: f0,f1,… -> feature symbol
    rules.{psv,md,json}                  # run-global dictionary: r0,r1,… -> rule symbol
    actions.{psv,md,json}                # run-global dictionary: a0,a1,… -> ground action
    atoms.{psv,md,json}                  # run-global dictionary: p0,p1,… -> ground atom (+ kind)
  failures/
    <id>/                                # <id> already encodes the category (e.g. open_state-001, cycle-001)
      meta.json                          # per-failure metadata (see docs/index.md)
      witness.{psv,md,json}              # witness state or cycle
      trace.{psv,md,json}                # path to the witness, present when a path exists
      successors.{psv,md,json}           # 1-step successors of the witness
```

