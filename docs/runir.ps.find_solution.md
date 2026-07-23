# runir.ps.find_solution

`find_solution(...)` validates either a base sketch policy or an extended module program. The candidate type selects the result type and table schema.

## Python Call

```python
result = find_solution(
    task_context,
    candidate,
    classifier=None,
    universal=False,
    num_rollouts=1,
    random_seed=0,
    random_seed_start=0,
    shuffle_choice_points=True,
    search_budget=None,
    plan_trace_budget=SearchBudget(
        max_num_states=1_000_000,
        max_time_seconds=10.0,
    ),
)
```

Passing a `Policy` returns `FindPolicySolutionResult`; passing a `ModuleProgram` returns `FindModuleProgramSolutionResult`. Dump either result with `dump_result(result, output_dir, formats=(DumpFormat.PSV, DumpFormat.MD, DumpFormat.JSON))`. The dump-only `include_witness`, `include_witness_trace`, `include_plan_trace`, and `include_successors` flags independently disable those evidence builders without changing validation. If all four are false, the dump contains a task-only failure row and constructs no evidence dictionaries or artifacts.

## Arguments

| Name | Type | Default | Description |
|---|---|---|---|
| `task_context` | `TaskContext` | required | Parsed and grounded task context returned by `create_task_context(...)`. |
| `candidate` | `Policy | ModuleProgram` | required | Candidate returned by `create_policy(...)` or `create_module_program(...)`. |
| `classifier` | `Classifier | None` | `None` | Optional unsolvability classifier. A classifier-positive non-goal state is terminal; goals take precedence. |
| `universal` | `bool` | `False` | Select existential rollout mode (`False`) or universal proof mode (`True`). |
| `num_rollouts` | `int` | `1` | Existential rollout count, or universal regular-evidence capacity. Must be at least 1. |
| `random_seed` | `int` | `0` | Seed for one rollout or the universal search. |
| `random_seed_start` | `int` | `0` | First seed when existential mode requests multiple rollouts. |
| `shuffle_choice_points` | `bool` | `True` | Shuffle policy or module-program choice points using the selected seed. |
| `search_budget` | `SearchBudget | None` | `None` | Search budget. `None` selects the mode-specific default described below. |
| `plan_trace_budget` | `SearchBudget` | 1,000,000 states, 10 s | FF budget used by `dump_result(...)` for an open-state plan trace. |

## Search Modes

With `universal=False`, Runir performs `num_rollouts` native greedy searches. One rollout uses `random_seed`; multiple rollouts use consecutive seeds beginning at `random_seed_start`. The default search budget is unconstrained.

With `universal=True`, Runir performs one exhaustive search. The default search budget is 100,000 states and 5 seconds. `num_rollouts = n` limits regular evidence, not searches:

- report at most `n` non-cycle counterexamples;
- if only `i < n` non-cycle counterexamples exist, fill the remaining `n-i` slots with successful witness traces;
- report at most one cycle as additional evidence, outside the `n`-item limit.

Thus a universal result contains at most `n` regular evidence items plus one cycle. Counterexamples are selected before successful witness traces.

Native terminal vertices, whether intrinsically dead or stopped by the optional classifier, are reported as `deadend`. Ordinary unfinished frontier vertices are reported as `open_state`. Resource exhaustion remains in the native `status`; it is not an evidence category.

## Output

State rows contain feature values and `fluent`/`derived` facts for witness and cycle states. A witness trace follows the Runir proof/execution graph to a failure witness or goal; an open-state plan trace is separate FF evidence from the witness state. Transition rows contain action labels and matched rule symbols. Proof labels do not carry heuristic values; `hstar` and `hlmcut` appear only in artifacts backed by an explicit state-evidence evaluator, such as open-state FF plan traces.

- Policies use the [base sketch-policy tables](tables/runir.ps.base.counterexamples.md).
- Module programs use the [module-program tables](tables/runir.ps.ext.counterexamples.md), including module and memory control state.
- Open-state `plan_trace.*` files use the [FF plan-trace tables](tables/runir.ps.open_state.plan_trace.md).
- `summary.*`, `failures.*`, and `successes.*` use the [solution index tables](tables/index-tables.md).

## Output Directory

```text
output_dir/
  .pyrunir-mcp-output
  manifest.json                          # metadata and artifact paths; JSON only
  summary.{psv,md,json}                  # selected evidence index
  failures.{psv,md,json}                 # non-cycle failures and optional extra cycle
  successes.{psv,md,json}                # selected successful witness traces
  dicts/
    features.{psv,md,json}
    rules.{psv,md,json}
    actions.{psv,md,json}
    atoms.{psv,md,json}
    modules.{psv,md,json}                # module programs only
    memory.{psv,md,json}                 # module programs only
  failures/
    <id>/
      witness.{psv,md,json}              # present when enabled
      witness_trace.{psv,md,json}        # present when enabled and a path exists
      successors.{psv,md,json}           # present when successors exist
      plan_trace.{psv,md,json}           # open states when FF finds a plan
  successes/
    <id>/
      witness_trace.{psv,md,json}
```

The sectioned artifact header uses `@tool runir.ps.find_solution`; the validation kind distinguishes base from extended results. Success entries contain only a complete witness trace. Failure rows remain present when standalone witnesses are disabled, with a null witness path. With all evidence disabled, `summary.*` and `failures.*` contain one row whose only non-null value is `task_file`; `dicts/`, `failures/`, and `successes/` are absent. Schema-v2 `manifest.json` records all four evidence flags explicitly, including `solution_witness`, while `result.json` retains machine routing metadata.
