# Tables: base-policy termination counterexamples

Used by [`runir.ps.base.prove_termination`](../runir.ps.base.prove_termination.md). Rendering conventions are in [Table Rendering](rendering.md).

A termination counterexample is a cycle in the structural termination graph. It contains no planning states, actions, traces, successors, or memory states.

## Dictionary Tables

`dicts/variables.*` maps each `vK` to `kind` (`boolean` or `numerical`) and the declared feature `symbol`. `dicts/rules.*` maps each `rK` to a policy-rule `symbol`. No memory dictionary is emitted.

## Section Tables

- `[cycle]`: `vertex_indices` is the closed vertex sequence; `edge_indices` is the corresponding edge sequence.
- `[vertices]`: `vertex_index` followed by one `vK` column per feature. Boolean cells are `T`/`F`; numerical cells are `>0`/`=0`.
- `[edges]`: `edge_index`, `source_vertex_index`, `target_vertex_index`, `rule_id`, and `deltas`. Each delta is `vK:<change>`, where the change is `unconstrained`, `increases`, `decreases`, or `unchanged`.
