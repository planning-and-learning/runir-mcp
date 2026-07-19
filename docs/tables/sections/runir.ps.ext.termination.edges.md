# Section Table: termination `[edges]`

Used by: [`../runir.ps.ext.prove_termination.md`](../runir.ps.ext.prove_termination.md).

Edges in the structural termination cycle.

| Column | Meaning |
|---|---|
| `edge_index` | Edge index within the witness. |
| `source_vertex_index` | Source vertex index. |
| `target_vertex_index` | Target vertex index. |
| `rule_id` | Module-rule alias (`rK`) from [`rules.*`](../dictionaries/runir.ps.ext.termination.rules.md). |
| `deltas` | Space-separated Boolean and numerical movements. `vK?` is unconstrained, `vK=` unchanged, `vK↑` increasing or becoming true, and `vK↓` decreasing or becoming false. Boolean movements are derived from the selected source and target; numerical movements come from the qualitative rule effect. |

Rows follow cycle order. The final edge targets the first vertex; a self-loop contains one row.
