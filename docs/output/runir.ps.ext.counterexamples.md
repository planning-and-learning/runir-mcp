# Output: module-program counterexamples, traces, and successors

Shared output-file format for the extended module-program tools — [`runir.ps.ext.execute_module_program`](../runir.ps.ext.execute_module_program.md) and [`runir.ps.ext.prove_module_program`](../runir.ps.ext.prove_module_program.md).

This format **mirrors the [base sketch-policy output format](runir.ps.base.counterexamples.md)** — same `.psv`/`.md`/`.json` renderings, the same [conventions](runir.ps.base.counterexamples.md#conventions) (pipe tables, `@key value` headers, interning, `T`/`F`, …), and the same [flag vocabulary](runir.ps.base.counterexamples.md#section-reference). This page documents only what module programs add: the **module/memory control dimension**. (Termination proofs use a different witness shape and stay documented inline in [`prove_termination`](../runir.ps.ext.prove_termination.md).)

## What module programs add

A module-program proof node is a **vertex** = (planning state, memory location), where a memory location is a `(module, memory-state)` pair. Consequences:

- A new **`memory` dictionary** interns the memory locations, alias `mK`.
- **`rules`** are module rules: each carries the memory-state transition it performs.
- State rows are keyed by **`vtx`** (the vertex), and carry both the planning **`state`** (where facts/features come from) and the memory location **`mem`**. The same planning state can appear under several memory locations, so `[transitions]`, `[cycle]`, and `[successors]` reference `vtx`, while `[facts]` stays keyed by `state` (shared across vertices).

## Dictionaries

Same idea as base, with one extra file (`memory`) and richer `rules`:

| Alias | File | Columns | Notes |
|---|---|---|---|
| `fK` | `features.*` | `id\|symbol` | Module-program and per-module features; ordered, drives `[state]`/`[states]` columns. |
| `rK` | `rules.*` | `id\|symbol\|src\|tgt` | Module rule; `src`/`tgt` are memory aliases (`mK`), so the module is recoverable from them. |
| `aK` | `actions.*` | `id\|action` | Ground actions. |
| `pK` | `atoms.*` | `id\|kind\|atom` | `kind` is `fluent`/`derived`/`static`. |
| `mK` | `memory.*` | `id\|module\|memory\|kind` | A `(module, memory-state)` control location; `kind` e.g. `initial`/`accepting`/inner. |

```text
# features.psv
id|symbol
f0|n_undeliv
f1|n_held

# rules.psv
id|symbol|src|tgt
r0|pickup|m0|m0
r1|advance|m0|m1

# actions.psv
id|action
a0|(pickup ball1 roomA)
a1|(drop ball1 roomB)

# atoms.psv
id|kind|atom
p0|fluent|at(robot roomA)
p1|fluent|holding(ball1)
p2|static|adjacent(roomA roomB)

# memory.psv
id|module|memory|kind
m0|deliver|q_init|initial
m1|deliver|q_done|accepting
```

## Counterexamples

Header lines are as in base (`@tool`, `@id`, `@category`, …). Sections carry the witness.

**State witness** — one `[state]` section plus its facts:

```text
[state]
vtx|state|mem|flags|f0|f1
7|42|m1|WITNESS|3|0

[facts]
state|atoms
42|p0,p1,p2
```

**Cycle witness** — a `[cycle]` descriptor (over vertices) plus the states and transitions on the cycle:

```text
[cycle]
key|value
cycle_vertex_indices|3,5,3
cycle_state_indices|10,11,10

[states]
vtx|state|mem|flags|f0|f1
3|10|m0|CYCLE|2|1
5|11|m1|CYCLE|2|0

[transitions]
step|src|tgt|rule|action|delta
0|3|5|r1|a1|f1:1>0
1|5|3|r0|a0|f1:0>1

[facts]
state|atoms
10|p1
11|p0
```

`[transitions]` `src`/`tgt` are **vertex** indices; the planning-state path is read from the `[states]` table's `state` column.

## Traces

Same as base, with the `vtx|state|mem|flags|…` state columns and vertex-indexed transitions:

```text
@tool execute_module_program
@id cycle-001
@category cycle
@problem p01.pddl

[states]
vtx|state|mem|flags|f0|f1
0|0|m0|INIT|3|0
1|1|m0||2|1
3|10|m1|CYCLE|2|0

[transitions]
step|src|tgt|rule|action|delta
0|0|1|r0|a0|f1:0>1
1|1|3|r1|a1|f0:3>2 f1:1>0

[facts]
state|atoms
0|p0
1|p1
```

## Successors

> **Note:** module programs do not yet emit the generator-expanded frontier that base sketches do. Determining which module rule permits a `(state, memory)` transition needs a compatibility primitive that `pyrunir.kr.ps.ext` does not currently expose, so ext successors remain the witness's **graph-derived compatible transitions** (the moves already in the proof graph), not the full applicable-move frontier. The schema below is unchanged; only the source of the rows differs.

Same purpose and categories as [base successors](runir.ps.base.counterexamples.md#successors) — the 1-step frontier from the witness, the gap visible as an advancing successor with an empty `rule`. `src`/`tgt` are vertices:

```text
[successors]
src|action|tgt|rule|flags|delta
3|a5|9|r1|GOAL|f0:2>1 f1:1>0
5|a6|11||DEADEND|f1:0>1

[states]
vtx|state|mem|flags|f0|f1
9|20|m1|GOAL|1|0
11|21|m1|DEADEND|2|1

[facts]
state|atoms
20|p0,p1
21|p0
```

As in base, the `[successors]` rows are followed by a `[states]` table (the full feature vector of each successor target) and a `[facts]` table (its `fluent`/`derived` atoms). When several features change on one move, the `delta` cell lists them space-separated (`f0:2>1 f1:1>0`), changed features only — unchanged features are omitted.

## Section reference

| Section | Columns | Notes |
|---|---|---|
| `[state]` | `vtx\|state\|mem\|flags\|f0\|f1\|…` | Single witness vertex; `vtx` vertex index, `state` planning state, `mem` is `mK`. |
| `[states]` | `vtx\|state\|mem\|flags\|f0\|f1\|…` | Vertices, wide; feature column order from `features.*`. |
| `[transitions]` | `step\|src\|tgt\|rule\|action\|delta` | `src`/`tgt` are **vertex** indices; `rule` is `rK` (module rule). |
| `[facts]` | `state\|atoms` | Keyed by **planning state** (shared across vertices); `pK` list of fluent/derived atoms. |
| `[cycle]` | `key\|value` | `cycle_vertex_indices` and `cycle_state_indices`. |
| `[successors]` | `src\|action\|tgt\|rule\|flags\|delta` | `src`/`tgt` are vertices; cycle/deadend scoping as in base. |

`fK`/`rK`/`aK`/`pK`/`mK` aliases resolve against the run-global [dictionaries](#dictionaries). The `flags` vocabulary is the [same as base](runir.ps.base.counterexamples.md#section-reference).
