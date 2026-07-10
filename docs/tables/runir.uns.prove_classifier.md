# Tables: unsolvability-classifier counterexamples

Used by [`runir.uns.prove_classifier`](../runir.uns.prove_classifier.md) as the classifier witness table design. Rendering conventions are in [Table Rendering](rendering.md).

A classifier counterexample is a single misclassified witness state. There are no transitions, cycles, traces, or successors.

A classifier predicts whether a state is unsolvable. `false_positive` means it predicted unsolvable for a solvable state; `false_negative` means it predicted solvable for an unsolvable state.

## Dictionary Tables

Run-global dictionary files live under `dicts/`.

- [`features.*`](dictionaries/runir.uns.features.md)
- [`atoms.*`](dictionaries/runir.uns.atoms.md)

## Index Tables

See [classifier `failures.*`](indexes/runir.uns.failures.md) for the classifier mistake index table design.

## Section Tables

- [`[states]`](sections/runir.uns.states.md)
- [`[facts]`](sections/runir.uns.facts.md)

The verdict is carried by the `@category` header and the failure id prefix.
