# Tables: module-program counterexamples, traces, and successors

Used by [`runir.ps.ext.execute_module_program`](../runir.ps.ext.execute_module_program.md) and [`runir.ps.ext.prove_module_program`](../runir.ps.ext.prove_module_program.md). Rendering conventions are in [Table Rendering](rendering.md).

Module-program output mirrors the base sketch-policy output tables, with an added module/memory control dimension. A graph vertex is `(planning state, memory location)`.

A memory location is a `(module, memory-state)` pair. Memory-state names are scoped by module, so the public tables identify control states by the tuple `state|module|memory`: planning state (`sK`) plus module (`MK`) plus memory location (`mK`).

## Dictionary Tables

Run-global dictionary files live under `dicts/`.

- [`features.*`](dictionaries/runir.ps.ext.features.md)
- [`rules.*`](dictionaries/runir.ps.ext.rules.md)
- [`actions.*`](dictionaries/runir.ps.ext.actions.md)
- [`atoms.*`](dictionaries/runir.ps.ext.atoms.md)
- [`modules.*`](dictionaries/runir.ps.ext.modules.md)
- [`memory.*`](dictionaries/runir.ps.ext.memory.md)

## Section Tables

- [`[states]`](sections/runir.ps.ext.states.md)
- [`[transitions]`](sections/runir.ps.ext.transitions.md)
- [`[facts]`](sections/runir.ps.ext.facts.md)
- [`[successors]`](sections/runir.ps.ext.successors.md)

`hstar` and `hlmcut` have the same meaning as in the base policy tables. Flags use the [base flag vocabulary](sections/runir.ps.base.flags.md).

## Artifact Documents

`witness.*` contains a single witness control state or a cycle. State witnesses use `[states]` plus `[facts]`; cycle witnesses use `[states]`, `[transitions]`, and `[facts]`. In cycle witnesses, `[states]` is a closed path: the first control-state row is repeated as the final row.

`trace.*` uses tuple-indexed `[states]` and `[transitions]`, plus planning-state `[facts]`.

`successors.*` contains the one-step frontier from each source control location on the trace/cycle. Generated successors are off-graph, so both source and target are represented as planning state plus control location: `source_state_id`/`source_module_id`/`source_memory_id` and `target_state_id`/`target_module_id`/`target_memory_id`. For a gap, `rule_id`, `target_module_id`, and `target_memory_id` are blank.

`plan_trace.*` uses the shared [open-state FF plan trace](runir.ps.open_state.plan_trace.md) schema. It is planner evidence from an open-state witness, not module-program execution.

Successful rollout traces use the module-program trace schema and contain no witness or successor frontier.
