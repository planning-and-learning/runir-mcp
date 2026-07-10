# Section Table: termination `[edges]`

Used by: [`../runir.ps.ext.prove_termination.md`](../runir.ps.ext.prove_termination.md).

Edges in the structural termination cycle.

| Column | Meaning |
|---|---|
| `edge_index` | Edge index within the witness. |
| `source_vertex_index` | Source vertex index. |
| `target_vertex_index` | Target vertex index. |
| `rule_id` | Module-rule alias (`rK`) from [`rules.*`](../dictionaries/runir.ps.ext.termination.rules.md). |
| `deltas` | Space-separated numerical movements as `vK:<change>`, changed numericals only. |
