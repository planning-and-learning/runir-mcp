# Dictionary: termination `variables.*`

Used by: [`../runir.ps.ext.prove_termination.md`](../runir.ps.ext.prove_termination.md).

| Column | Meaning |
|---|---|
| `id` | Variable alias, rendered as `vK`. |
| `kind` | Variable kind: `concept`, `boolean`, or `numerical`. |
| `symbol` | Structural-termination variable symbol. |

Rows are ordered and define the `v0`, `v1`, ... columns in `[vertices]`. Vertex cell values follow the variable kind: concept denotations, `T`/`F` booleans, or integer numericals.
