# Dictionary: classifier `atoms.*`

Used by: [`../runir.uns.prove_classifier.md`](../runir.uns.prove_classifier.md).

| Column | Meaning |
|---|---|
| `id` | Atom alias, rendered as `pK`. |
| `kind` | Atom kind: `static`, `fluent`, or `derived`. |
| `atom` | Ground atom text using the planner/formalism default formatting. |

Classifier witnesses use `[facts]` to list the misclassified state's fluent/derived atoms as comma-separated `pK` aliases. Static atoms are present in `atoms.*` when seen in checked states but are not repeated in per-state `[facts]` rows.
