# runir.ps.base.prove_policy

## Python Call

```python
result = prove_policy(
    task_context,
    policy,
    classifier=None,
    search_budget=SearchBudget(max_num_states=100_000, max_time_seconds=5.0),
    plan_trace_budget=SearchBudget(max_num_states=1_000_000, max_time_seconds=10.0),
)
```

Dump with `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.MD, DumpFormat.JSON))`.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`; contains its parent `DomainContext`. |
| `policy` | `Policy` | required | Policy candidate returned by `create_policy(...)` or `write_empty_policy(...)`. |
| `classifier` | `Classifier | None` | `None` | Optional unsolvability classifier candidate returned by `create_classifier(...)`. |
| `search_budget` | `SearchBudget` | `SearchBudget(max_num_states=100_000, max_time_seconds=5.0)` | Proof search budget; both fields must be set. |
| `plan_trace_budget` | `SearchBudget` | `SearchBudget(max_num_states=1_000_000, max_time_seconds=10.0)` | FF plan-trace budget used by `dump_result(...)` for reported open-state failures. |

## Output / Dump Artifacts
`hstar` is exact remaining lifted plan length in actions (`inf` = proven dead, empty = budget exhausted). `hlmcut` is the raw LM-cut lower bound for the same lifted state.

Counterexample output keeps one representative open state, one representative deadend transition, and one cycle if present; cycle does not count against the other categories.

Dictionaries and per-failure files use the [base sketch-policy table schema](tables/runir.ps.base.counterexamples.md). `plan_trace.*` uses the [open-state FF plan trace schema](tables/runir.ps.open_state.plan_trace.md) and is generated during dumping when FF finds a plan from an open-state witness. `result.json` records both `search_budget` and `plan_trace_budget`; plan traces use the latter, not the proof budget. `summary.*` uses the [native summary table](tables/indexes/native.summary.md); `run.json` is JSON-only run metadata. Failure categories: `open_state`, `deadend_transition`, `cycle`. Proof has no rollout seeds, so no `@seed` header.

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  run.json                               # run envelope: metadata, counts, artifact paths (JSON only)
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
      plan_trace.{psv,md,json}           # FF plan trace from an open-state witness, when available
```

