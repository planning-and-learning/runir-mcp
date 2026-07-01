# runir.ps.ext.prove_module_program

## Python Call

```python
result = prove_module_program(
    task_context,
    module_program,
    classifier=None,
    max_num_states=100_000,
    max_time_seconds=5.0,
    max_arity=0,
)
```

Dump with `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.MD, DumpFormat.JSON))`.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`; contains its parent `DomainContext`. |
| `module_program` | `ModuleProgram` | required | Module-program candidate returned by `create_module_program(...)`. |
| `classifier` | `Classifier | None` | `None` | Optional unsolvability classifier candidate returned by `create_classifier(...)`. |
| `max_num_states` | `int` | `100_000` | Proof search state budget. |
| `max_time_seconds` | `float` | `5.0` | Proof wall-clock budget in seconds. |
| `max_arity` | `int` | `0` | Maximum module-program arity. |

## Output / Dump Artifacts
`hstar` is exact remaining lifted plan length in actions (`inf` = proven dead, empty = budget exhausted). `hlmcut` is the raw LM-cut lower bound.

Counterexamples are bounded by category: at most `max_open_state_counterexamples`, at most `max_deadend_transition_counterexamples`, and one cycle if present; cycle does not count against the other bounds.

Dictionaries and per-failure files use the [module-program output format](output/runir.ps.ext.counterexamples.md). `summary.*` indexes them; `manifest.json` is JSON-only metadata. Failure categories: `open_state`, `deadend_transition`, `cycle`. Proof has no rollout seeds, so no `@seed` header.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # run metadata: config, proof budgets, hstar budgets (JSON only)
  summary.{psv,md,json}                  # run index/counts table
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
      successors.{psv,md,json}           # 1-step successors of the witness
```

