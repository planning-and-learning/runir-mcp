# Tables: module-program termination counterexamples

Used by [`runir.ps.ext.prove_termination`](../runir.ps.ext.prove_termination.md). Rendering conventions are in [Table Rendering](rendering.md).

A termination counterexample is the first directed cycle found in the residual structural-termination graph. Only that cycle's vertices and edges are emitted; unrelated outgoing edges are omitted. A self-loop is a valid one-edge cycle.

The files report the cycle and how variables change along it; they do not decide which measure ought to decrease.

## Dictionary Tables

Run-global dictionary files live under `dicts/`.

- [`variables.*`](dictionaries/runir.ps.ext.termination.variables.md)
- [`memory.*`](dictionaries/runir.ps.ext.termination.memory.md)
- [`rules.*`](dictionaries/runir.ps.ext.termination.rules.md)

## Section Tables

- [`[vertices]`](sections/runir.ps.ext.termination.vertices.md)
- [`[edges]`](sections/runir.ps.ext.termination.edges.md)

The rows of both tables are ordered along the cycle. The final edge targets the first vertex.

