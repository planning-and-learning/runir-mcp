# Section Table: classifier `[state]`

Used by: [`../runir.uns.prove_classifier.md`](../runir.uns.prove_classifier.md).

Single misclassified classifier witness state.

| Column | Meaning |
|---|---|
| `id` | Planning-state id (`sK`). |
| `flags` | State flags, usually `WITNESS`. |
| `f0`, `f1`, ... | Boolean classifier feature values, one column per row in [`features.*`](../dictionaries/runir.uns.features.md). |

The verdict is carried by the `@category` header and failure id prefix, not by this table.
