# Tables: base sketch-policy counterexamples, traces, and successors

Used by base-policy calls to [`runir.ps.find_solution`](../runir.ps.find_solution.md). Rendering conventions are in [Table Rendering](rendering.md).

## Dictionary Tables

Run-global dictionary files live under `dicts/`. Every witness, trace, and successor file references these aliases.

- [`features.*`](dictionaries/runir.ps.base.features.md)
- [`rules.*`](dictionaries/runir.ps.base.rules.md)
- [`actions.*`](dictionaries/runir.ps.base.actions.md)
- [`atoms.*`](dictionaries/runir.ps.base.atoms.md)

## Section Tables

- [`[states]`](sections/runir.ps.base.states.md)
- [`[transitions]`](sections/runir.ps.base.transitions.md)
- [`[facts]`](sections/runir.ps.base.facts.md)
- [`[successors]`](sections/runir.ps.base.successors.md)

Proof labels do not carry heuristic values. Optional `hstar` and `hlmcut` columns are included only when an explicit state-evidence evaluator supplies them.

Cycle witnesses use `[states]`, `[transitions]`, and `[facts]`; `[states]` is a closed path with the first state row repeated as the final row.

`plan_trace.*` uses the shared [open-state FF plan trace](runir.ps.open_state.plan_trace.md) schema. It is planner evidence from an open-state witness, not policy execution.



## Flag Values

See [base `flags`](sections/runir.ps.base.flags.md).
