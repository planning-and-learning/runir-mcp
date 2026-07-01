# Dictionary: module-program `atoms.*`

Used by: [`../runir.ps.ext.counterexamples.md`](../runir.ps.ext.counterexamples.md).

| Column | Meaning |
|---|---|
| `id` | Atom alias, rendered as `pK`. |
| `kind` | Atom kind: `fluent`, `derived`, or `static`. |
| `atom` | Ground atom text. |

`[facts]` rows are keyed by planning state (`sK`) and list per-state `fluent` and `derived` atoms as comma-separated `pK` aliases. `static` atoms are interned here and not repeated in `[facts]`.
