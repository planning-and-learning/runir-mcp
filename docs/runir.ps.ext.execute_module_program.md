# runir.ps.ext.execute_module_program

## Python Call

```python
result = execute_module_program(
    task_context,
    module_program,
    classifier=None,
    num_rollouts=1,
    random_seed=0,
    random_seed_start=0,
    shuffle_labeled_succ_nodes=True,
    max_arity=0,
    max_num_states=None,
    max_time_seconds=None,
)
```

Dump with `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.MD, DumpFormat.JSON))`.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`; contains its parent `DomainContext`. |
| `module_program` | `ModuleProgram` | required | Module-program candidate returned by `create_module_program(...)`. |
| `classifier` | `Classifier | None` | `None` | Optional unsolvability classifier candidate returned by `create_classifier(...)`. |
| `num_rollouts` | `int` | `1` | Number of rollout seeds to execute. |
| `random_seed` | `int` | `0` | Seed used when `num_rollouts == 1`. |
| `random_seed_start` | `int` | `0` | First seed used when `num_rollouts > 1`. |
| `shuffle_labeled_succ_nodes` | `bool` | `True` | Shuffle successor labels during rollout search. |
| `max_arity` | `int` | `0` | Maximum module-program arity. |
| `max_num_states` | `int | None` | `None` | Per-subgoal state budget. |
| `max_time_seconds` | `float | None` | `None` | Per-subgoal wall-clock budget in seconds. |

## Output / Dump Artifacts
Same structure as `runir.ps.base.execute_policy`, with module/memory control state. `hstar` and `hlmcut` have the same semantics as base. Dictionaries, failures, successors, and success traces use the [module-program table schema](tables/runir.ps.ext.counterexamples.md).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # run metadata: config, command, rollout budgets, hstar budgets (JSON only)
  summary.{psv,md,json}                  # run index/counts table
  failures.{psv,md,json}                 # one row per representative failure (index)
  successes.{psv,md,json}                # one row per successful rollout trace (index)
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
      witness.{psv,md,json}              # witness vertex or cycle
      trace.{psv,md,json}                # path to the witness, present when a path exists
      successors.{psv,md,json}           # 1-step successors of the witness (open_state, cycle, deadend)
  successes/
    <id>/                                # one directory per successful rollout
      meta.json                          # per-success metadata (see docs/index.md)
      trace.{psv,md,json}                # complete successful rollout trace; no witness/successors
```

## Output Files

The shared [module-program table schema](tables/runir.ps.ext.counterexamples.md) defines dictionaries and per-failure files. Rendering rules are in [Table Rendering](tables/rendering.md). Execute-specific details:

- `source` is `find_solution`; `seed` is the rollout seed.
- Successors are emitted in full (never truncated) for `open_state`, `cycle`, and `deadend` witnesses.

`failures`, `successes`, and `summary` indexes match `execute_policy`; their columns are defined in [Index Tables](tables/index-tables.md). `manifest.json` is JSON-only metadata.


Successful rollout entries are trace-only: `meta.json` and `trace.*`, no `witness` or `successors`; all successful seeds are listed.
