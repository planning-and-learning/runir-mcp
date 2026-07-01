# Section Table: termination `[vertices]`

Used by: [`../runir.ps.ext.prove_termination.md`](../runir.ps.ext.prove_termination.md).

Abstract vertices in the structural termination graph.

| Column | Meaning |
|---|---|
| `idx` | Vertex index within the witness. |
| `mem` | Memory-state alias (`mK`) from [`memory.*`](../dictionaries/runir.ps.ext.termination.memory.md). |
| `v0`, `v1`, ... | Variable values, one column per row in [`variables.*`](../dictionaries/runir.ps.ext.termination.variables.md). |

Variable values follow the variable kind: concept denotation, `T`/`F` boolean, or integer numerical value.
