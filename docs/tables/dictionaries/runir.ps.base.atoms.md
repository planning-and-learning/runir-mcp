# Dictionary: base `atoms.*`

Used by: [`../runir.ps.base.counterexamples.md`](../runir.ps.base.counterexamples.md).

| Column | Meaning |
|---|---|
| `id` | Atom alias, rendered as `pK`. |
| `kind` | Atom kind: `fluent`, `derived`, or `static`. |
| `atom` | Ground atom text. |

`[facts]` rows list per-state `fluent` and `derived` atoms as comma-separated `pK` aliases. `static` atoms hold in every state, so they are interned here and not repeated in `[facts]`.
