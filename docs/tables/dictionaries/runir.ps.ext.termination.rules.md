# Dictionary: termination `rules.*`

Used by: [`../runir.ps.ext.prove_termination.md`](../runir.ps.ext.prove_termination.md).

| Column | Meaning |
|---|---|
| `id` | Rule alias, rendered as `rK`. |
| `symbol` | Module rule symbol. |

Rule aliases appear in `[edges]`. Unlike module-program counterexample rules, termination rules do not carry source/target memory columns; the edge itself carries `src` and `tgt` vertex indices.
