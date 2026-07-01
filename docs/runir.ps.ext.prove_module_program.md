# runir.ps.ext.prove_module_program

## Python Call

```python
result = prove_module_program(
    task_context,
    module_program,
    classifier=None,
    search_budget=SearchBudget(max_num_states=100_000, max_time_seconds=5.0),
    plan_trace_budget=SearchBudget(max_num_states=1_000_000, max_time_seconds=10.0),
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
| `search_budget` | `SearchBudget` | `SearchBudget(max_num_states=100_000, max_time_seconds=5.0)` | Proof search budget; both fields must be set. |
| `plan_trace_budget` | `SearchBudget` | `SearchBudget(max_num_states=1_000_000, max_time_seconds=10.0)` | FF plan-trace budget used by `dump_result(...)` for reported open-state failures. |
| `max_arity` | `int` | `0` | Maximum module-program arity. |

## Output / Dump Artifacts
`hstar` is exact remaining lifted plan length in actions (`inf` = proven dead, empty = budget exhausted). `hlmcut` is the raw LM-cut lower bound.

Counterexamples are bounded by category: at most `max_open_state_counterexamples`, at most `max_deadend_transition_counterexamples`, and one cycle if present; cycle does not count against the other bounds.

Dictionaries and per-failure files use the [module-program table schema](tables/runir.ps.ext.counterexamples.md). `plan_trace.*` uses the [open-state FF plan trace schema](tables/runir.ps.open_state.plan_trace.md) and is generated during dumping when FF finds a plan from an open-state witness. `result.json` records both `search_budget` and `plan_trace_budget`; plan traces use the latter, not the proof budget. `summary.*` uses the [native summary table](tables/indexes/native.summary.md); `run.json` is JSON-only run metadata. Failure categories: `open_state`, `deadend_transition`, `cycle`. Proof has no rollout seeds, so no `@seed` header.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  run.json                               # run envelope: metadata, counts, artifact paths (JSON only)
  summary.{psv,md,json}                  # run index/counts table
  dicts/
    features.{psv,md,json}               # run-global dictionary: f0,f1,… -> feature symbol
    rules.{psv,md,json}                  # run-global dictionary: r0,r1,… -> module rule (+ src/tgt memory)
    actions.{psv,md,json}                # run-global dictionary: a0,a1,… -> ground action
    atoms.{psv,md,json}                  # run-global dictionary: p0,p1,… -> ground atom (+ kind)
    modules.{psv,md,json}                # run-global dictionary: M0,M1,… -> module name
    memory.{psv,md,json}                 # run-global dictionary: m0,m1,… -> (module, memory-state)
  failures/
    <id>/                                # <id> already encodes the category (e.g. open_state-001, cycle-001)
      meta.json                          # per-failure metadata (see docs/index.md)
      witness.{psv,md,json}              # witness control state or cycle
      trace.{psv,md,json}                # path to the witness, present when a path exists
      successors.{psv,md,json}           # 1-step successors of the witness
      plan_trace.{psv,md,json}           # FF plan trace from an open-state witness, when available
```

