# Values Table: base `flags`

Used by base and module-program state tables.

| Flag | Meaning |
|---|---|
| `init` | Initial state. |
| `goal` | Goal state. |
| `open` | Open / unexpanded state. |
| `witness` | Counterexample witness state. |
| `cycle` | State participating in the cycle. |
| `deadend` | Dead state: the goal is unreachable. |
