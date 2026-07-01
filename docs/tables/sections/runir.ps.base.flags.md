# Values Table: base `flags`

Used by base and module-program state tables.

| Flag | Meaning |
|---|---|
| `INIT` | Initial state. |
| `GOAL` | Goal state. |
| `OPEN` | Open / unexpanded state. |
| `WITNESS` | Counterexample witness state. |
| `CYCLE` | State participating in the cycle. |
| `DEADEND` | Dead state: the goal is unreachable. |
