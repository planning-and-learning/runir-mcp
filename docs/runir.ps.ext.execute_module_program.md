# runir.ps.ext.execute_module_program

## Python Call

```python
result = execute_module_program(
    domain_context,
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

Use `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.MD, DumpFormat.JSON))`
when filesystem artifacts are needed. Validation itself is in-memory.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parsed domain context returned by `create_domain_context(...)`. |
| `task_context` | `TaskContext` | required | Parsed/grounded task context returned by `create_task_context(...)`. |
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
Same normalized structure as `runir.ps.base.execute_policy`, with `tool: "runir.ps.ext.execute_module_program"`. `hstar` has the same semantics as base: shortest remaining lifted plan length in number of actions, `inf` for proven deadends, and empty when the per-state A*+LM-cut timeout/state budget is exhausted. `hlmcut` reports the raw LM-cut heuristic value for the same lifted planning state as an admissible lower bound, including when exact `hstar` is too costly. The dictionaries (under `dicts/`), the per-failure witness, trace, and successors files (under `failures/<id>/`), and trace-only successful rollout files (under `successes/<id>/`) use the shared [module-program output format](output/runir.ps.ext.counterexamples.md) (vertices carry their `(module, memory-state)` location).

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

The dictionaries under `dicts/` (`features`/`rules`/`actions`/`atoms`/`memory`) and the per-failure `witness`/`trace`/`successors` files use the shared [module-program output format](output/runir.ps.ext.counterexamples.md). This tool's specifics:

- `source` is `find_solution`; `seed` is the rollout seed.
- Successors are emitted in full (never truncated) for `open_state`, `cycle`, and `deadend` witnesses.

It also writes the `failures` index (one row per representative failure) and `successes` index (one row per successful rollout), identical in shape to `execute_policy`'s. Artifacts are written in the formats requested via `dump_result(..., formats=...)`; `summary.{psv,md,json}` is the run index and `manifest.json` holds run metadata (JSON-only).


Successful rollout entries are trace-only: each `successes/<id>/` directory contains `meta.json` and `trace.{psv,md,json}`, but no `witness` and no `successors`. All successful rollouts from the requested seeds are listed.
