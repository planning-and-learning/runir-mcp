# Tables: open-state FF plan trace

Used by base sketch-policy and module-program open-state failures when FF finds a plan from the witness planning state.

A `plan_trace.*` artifact is planner evidence, not policy or module-program execution. It records a task-level FF plan from the open state toward a goal. The policy/module-program did not select these steps, so the plan uses planning-state ids, action aliases, and feature deltas only: no rule, module, memory, or proof vertex columns.

For module-program failures, the open control context remains in `witness.*` and may be repeated in document headers such as `@start_module` and `@start_memory`; the FF plan rows themselves stay task-level. Plan-trace states are interned into the run-global `atoms.*` dictionary, including static atoms; `[facts]` lists per-state fluent and derived atom aliases.

## Dictionary Tables

The artifact reuses the run-global dictionaries for the producing tool.

- Base: [`features.*`](dictionaries/runir.ps.base.features.md), [`actions.*`](dictionaries/runir.ps.base.actions.md), [`atoms.*`](dictionaries/runir.ps.base.atoms.md)
- Module program: [`features.*`](dictionaries/runir.ps.ext.features.md), [`actions.*`](dictionaries/runir.ps.ext.actions.md), [`atoms.*`](dictionaries/runir.ps.ext.atoms.md)

## Section Tables

- [`[states]`](sections/runir.ps.plan_trace.states.md)
- [`[plan]`](sections/runir.ps.plan_trace.plan.md)
- [`[facts]`](sections/runir.ps.plan_trace.facts.md)

`hstar` is shortest remaining plan length, `inf` for proven deadends, and empty when inconclusive. `hlmcut` is the LM-cut lower bound for the same state. Plan-trace generation uses the run result's `plan_trace_budget`; the default is 1,000,000 states and 10 seconds.
