# Section Table: termination `[vertices]`

Used by: [`../runir.ps.ext.prove_termination.md`](../runir.ps.ext.prove_termination.md).

Abstract vertices in the structural termination graph.

| Column | Meaning |
|---|---|
| `vertex_index` | Vertex index within the witness. |
| `memory_id` | Memory-state alias (`mK`) from [`memory.*`](../dictionaries/runir.ps.ext.termination.memory.md). |
| `valuation` | Space-separated abstract literals. `vK` means true/positive and `¬vK` means false/zero. Aliases come from [`variables.*`](../dictionaries/runir.ps.ext.termination.variables.md). |

Rows follow cycle order. Each Boolean or numerical variable appears exactly once in every valuation.
