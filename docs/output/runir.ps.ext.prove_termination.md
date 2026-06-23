# Output: module-program termination counterexamples

Output-file format for [`runir.ps.ext.prove_termination`](../runir.ps.ext.prove_termination.md).

A non-termination witness is a **cycle in the structural termination graph** — abstract vertices (a memory state plus concept/boolean/numerical variable valuations) connected by module-rule edges that carry the numerical changes they cause. The cycle is the entire witness: there is no path-to-witness (`traces/`) and no successor frontier (`successors/`) — enumerating 1-step successors of these abstract vertices would be far too heavy.

The files **report the cycle and how the variables change along it**; they do not judge which measure ought to decrease. That diagnosis is left to the reader.

The encoding is the same PSV/Markdown/JSON format and [conventions](runir.ps.base.counterexamples.md#conventions) (pipe tables, `@key value` headers, interning, three renderings) used by the other tools, with the termination-specific schema below. The termination graph has no planning states, ground actions, or atoms, so there are no `features`/`actions`/`atoms` dictionaries and no `[facts]`; the abstract vertices carry **variables** in three kinds.

## Dictionaries

| Alias | File | Columns | Notes |
|---|---|---|---|
| `vK` | `variables.*` | `id\|kind\|symbol` | `kind` ∈ `concept`/`boolean`/`numerical`; ordered, drives `[vertices]` columns. |
| `mK` | `memory.*` | `id\|memory` | Memory state. |
| `rK` | `rules.*` | `id\|symbol` | Module rule on an edge. |

```text
# variables.psv
id|kind|symbol
v0|concept|c_undelivered
v1|boolean|b_holding
v2|numerical|n_count

# memory.psv
id|memory
m0|q_init

# rules.psv
id|symbol
r0|pickup
r1|advance
```

## Witness

`counterexamples/structural_termination/<id>.{psv,md,json}` — the non-termination cycle:

```text
@tool prove_termination
@id structural_termination-001
@category structural_termination
@status NON_TERMINATING
@module main

[cycle]
key|value
cycle_vertex_indices|0,1,0
cycle_edge_indices|0,1

[vertices]
idx|mem|v0|v1|v2
0|m0|{b1,b2}|T|3
1|m0|{b1}|T|2

[edges]
idx|src|tgt|rule|changes
0|0|1|r0|v2:dec
1|1|0|r1|v2:inc
```

- `[vertices]` columns are `idx|mem` followed by one column per variable in `variables.*` order. Values follow the variable's `kind`: concept → its denotation (e.g. a set), boolean → `T`/`F`, numerical → integer.
- `[edges]` `src`/`tgt` are vertex indices; `rule` is `rK`; `changes` is a space-separated list of `vK:<change>` for the numericals the edge moves, exactly as reported by the analysis (e.g. `v2:dec`), changed numericals only.

## Section reference

| Section | Columns | Notes |
|---|---|---|
| `[cycle]` | `key\|value` | `cycle_vertex_indices` and `cycle_edge_indices` describing the loop. |
| `[vertices]` | `idx\|mem\|v0\|v1\|…` | Abstract vertices; `mem` is `mK`, one `vK` column per variable. |
| `[edges]` | `idx\|src\|tgt\|rule\|changes` | `src`/`tgt` vertices; `rule` is `rK`; `changes` lists per-edge numerical movements (`vK:<change>`). |

`vK`/`mK`/`rK` aliases resolve against the run-global dictionaries above.
