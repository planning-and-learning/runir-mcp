# Tables: base-policy termination counterexamples

Used by [`runir.ps.base.prove_termination`](../runir.ps.base.prove_termination.md). Rendering conventions are in [Table Rendering](rendering.md).

A termination counterexample is the first directed cycle found in the residual structural-termination graph. Only that cycle's vertices and edges are emitted; unrelated outgoing edges are omitted. A self-loop is a valid one-edge cycle. It contains no planning states, actions, traces, successors, or memory states.

## Dictionary Tables

`dicts/variables.*` maps each `vK` to `kind` (`boolean` or `numerical`) and the declared feature `symbol`. `dicts/rules.*` maps each `rK` to a policy-rule `symbol`. No memory dictionary is emitted.

## Section Tables

- `[vertices]`: `vertex_index` and a compact `valuation`. `vK` means true/positive and `¬vK` means false/zero.
- `[edges]`: `edge_index`, `source_vertex_index`, `target_vertex_index`, `rule_id`, and `deltas`. Boolean movements are derived from the selected source and target; numerical movements come from the qualitative rule effect. They render as `vK?` (unconstrained), `vK=` (unchanged), `vK↑` (increases or becomes true), or `vK↓` (decreases or becomes false).

The rows of both tables are ordered along the cycle. The final edge targets the first vertex.
