# Tables: base sketch-policy counterexamples, traces, and successors

Used by [`runir.ps.base.execute_policy`](../runir.ps.base.execute_policy.md) and [`runir.ps.base.prove_policy`](../runir.ps.base.prove_policy.md). Rendering conventions are in [Table Rendering](rendering.md).

## Dictionary Tables

Run-global dictionary files live under `dicts/`. Every witness, trace, and successor file references these aliases.

- [`features.*`](dictionaries/runir.ps.base.features.md)
- [`rules.*`](dictionaries/runir.ps.base.rules.md)
- [`actions.*`](dictionaries/runir.ps.base.actions.md)
- [`atoms.*`](dictionaries/runir.ps.base.atoms.md)

## Section Tables

- [`[state]`](sections/runir.ps.base.state.md)
- [`[states]`](sections/runir.ps.base.states.md)
- [`[transitions]`](sections/runir.ps.base.transitions.md)
- [`[facts]`](sections/runir.ps.base.facts.md)
- [`[successors]`](sections/runir.ps.base.successors.md)

`hstar` is shortest remaining plan length, `inf` for proven deadends, and empty when inconclusive. `hlmcut` is the LM-cut lower bound for the same state.

Cycle witnesses use `[states]`, `[transitions]`, and `[facts]`; `[states]` is a closed path with the first state row repeated as the final row.



## Flag Values

See [base `flags`](sections/runir.ps.base.flags.md).
