# Tables: module-program termination counterexamples

Used by [`runir.ps.ext.prove_termination`](../runir.ps.ext.prove_termination.md). Rendering conventions are in [Table Rendering](rendering.md).

A termination counterexample is a cycle in the structural termination graph. There are no planning states, ground actions, atoms, traces, or successors.

The files report the cycle and how variables change along it; they do not decide which measure ought to decrease.

## Dictionary Tables

Run-global dictionary files live under `dicts/`.

- [`variables.*`](dictionaries/runir.ps.ext.termination.variables.md)
- [`memory.*`](dictionaries/runir.ps.ext.termination.memory.md)
- [`rules.*`](dictionaries/runir.ps.ext.termination.rules.md)

## Section Tables

- [`[cycle]`](sections/runir.ps.ext.termination.cycle.md)
- [`[vertices]`](sections/runir.ps.ext.termination.vertices.md)
- [`[edges]`](sections/runir.ps.ext.termination.edges.md)

Vertex values follow the variable kind: concept values render as denotations, booleans as `T`/`F`, and numerical values as integers.


