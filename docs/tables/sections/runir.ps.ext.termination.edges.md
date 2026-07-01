# Section Table: termination `[edges]`

Used by: [`../runir.ps.ext.prove_termination.md`](../runir.ps.ext.prove_termination.md).

Edges in the structural termination cycle.

| Column | Meaning |
|---|---|
| `idx` | Edge index within the witness. |
| `src` | Source vertex index. |
| `tgt` | Target vertex index. |
| `rule` | Module-rule alias (`rK`) from [`rules.*`](../dictionaries/runir.ps.ext.termination.rules.md). |
| `changes` | Space-separated numerical movements as `vK:<change>`, changed numericals only. |
