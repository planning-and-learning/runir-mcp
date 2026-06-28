# Output: module-program counterexamples, traces, and successors

Shared output-file format for the extended module-program tools — [`runir.ps.ext.execute_module_program`](../runir.ps.ext.execute_module_program.md) and [`runir.ps.ext.prove_module_program`](../runir.ps.ext.prove_module_program.md).

This format **mirrors the [base sketch-policy output format](runir.ps.base.counterexamples.md)** — same `.psv`/`.md`/`.json` renderings, the same [conventions](runir.ps.base.counterexamples.md#conventions) (pipe tables, `@key value` headers, interning, `T`/`F`, …), and the same [flag vocabulary](runir.ps.base.counterexamples.md#section-reference). This page documents only what module programs add: the **module/memory control dimension**. (Termination proofs use a different witness shape and stay documented inline in [`prove_termination`](../runir.ps.ext.prove_termination.md).)

## What module programs add

A module-program proof node is a **vertex** = (planning state, memory location), where a memory location is a `(module, memory-state)` pair. Consequences:

- A new **`modules` dictionary** interns the modules, alias `MK`.
- A new **`memory` dictionary** interns the memory states, alias `mK`. A memory-state name is only unique within a module (two modules can both have a `source` state), so each memory alias is keyed by `(module, memory-state)` and its row references the module alias `MK`.
- **`rules`** are module rules: each carries the memory-state transition it performs (`source`/`target` memory aliases).
- State rows are keyed by **`vertex`** (the vertex), and carry the planning **`state`** (where facts/features and `hstar`/`hlmcut` come from) plus the memory location as two columns — **`module`** (module alias `MK`) and **`memory`** (memory alias `mK`). The same planning state can appear under several memory locations, so `[transitions]` and `[cycle]` reference vertices, while `[facts]` stays keyed by `state` (shared across vertices). Ids are prefixed for readability: planning states render as `sK` (e.g. `s42`) and vertices as `vK` (e.g. `v3`) — these are id prefixes on the raw indices, not dictionary-backed aliases.

## Dictionaries

Same idea as base (all under `dicts/`), with two extra files (`modules`, `memory`) and richer `rules`:

| Alias | File | Columns | Notes |
|---|---|---|---|
| `fK` | `features.*` | `id\|symbol` | Module-program and per-module features; ordered, drives `[state]`/`[states]` columns. |
| `rK` | `rules.*` | `id\|symbol\|source\|target` | Module rule; `source`/`target` are memory aliases (`mK`). |
| `aK` | `actions.*` | `id\|action` | Ground actions. |
| `pK` | `atoms.*` | `id\|kind\|atom` | `kind` is `fluent`/`derived`/`static`. |
| `MK` | `modules.*` | `id\|module` | A module, by name. |
| `mK` | `memory.*` | `id\|module\|memory` | A `(module, memory-state)` control location; `module` is the module alias `MK` (names repeat across modules). |

```text
# dicts/features.psv
id|symbol
f0|n_undeliv
f1|n_held

# dicts/rules.psv
id|symbol|source|target
r0|pickup|m0|m0
r1|advance|m0|m1

# dicts/actions.psv
id|action
a0|(pickup ball1 roomA)
a1|(drop ball1 roomB)

# dicts/atoms.psv
id|kind|atom
p0|fluent|at(robot roomA)
p1|fluent|holding(ball1)
p2|static|adjacent(roomA roomB)

# dicts/modules.psv
id|module
M0|deliver

# dicts/memory.psv
id|module|memory
m0|M0|q_init
m1|M0|q_done
```

## Counterexamples

Header lines are as in base (`@tool`, `@id`, `@category`, …). Sections carry the witness.

**State witness** — one `[state]` section plus its facts:

```text
[state]
vertex|state|module|memory|flags|hstar|hlmcut|f0|f1
v7|s42|M0|m1|WITNESS|7|5|3|0

[facts]
state|atoms
s42|p0,p1,p2
```

**Cycle witness** — a `[cycle]` descriptor (over vertices) plus the states and transitions on the cycle:

```text
[cycle]
key|value
cycle_vertex_indices|v3,v5,v3
cycle_state_indices|s10,s11,s10

[states]
vertex|state|module|memory|flags|hstar|hlmcut|f0|f1
v3|s10|M0|m0|CYCLE|inf|inf|2|1
v5|s11|M0|m1|CYCLE|inf|inf|2|0

[transitions]
step|source|target|rule|action|delta
0|v3|v5|r1|a1|f1:1>0
1|v5|v3|r0|a0|f1:0>1

[facts]
state|atoms
s10|p1
s11|p0
```

`[transitions]` `source`/`target` are **vertex** ids (`vK`); the planning-state path is read from the `[states]` table's `state` column.

## Traces

Same as base, with the `vertex|state|module|memory|flags|hstar|hlmcut|…` state columns and vertex-indexed transitions:

```text
@tool execute_module_program
@id cycle-001
@category cycle
@problem p01.pddl

[states]
vertex|state|module|memory|flags|hstar|hlmcut|f0|f1
v0|s0|M0|m0|INIT|2|2|3|0
v1|s1|M0|m0||1|1|2|1
v3|s10|M0|m1|CYCLE|inf|inf|2|0

[transitions]
step|source|target|rule|action|delta
0|v0|v1|r0|a0|f1:0>1
1|v1|v3|r1|a1|f0:3>2 f1:1>0

[facts]
state|atoms
s0|p0
s1|p1
```


## Successful traces

Execute successful traces mirror base successful traces: `successes/<id>/trace.{psv,md,json}` uses the module-program trace schema above, with vertex-indexed `[states]`/`[transitions]` and planning-state `[facts]`. A success directory contains only `meta.json` and `trace.{psv,md,json}`; it has no witness and no successors.

## Successors

Same purpose and categories as [base successors](runir.ps.base.counterexamples.md#successors) — the 1-step frontier from each state on the trace/cycle, the gap visible as an advancing move with an empty `rule`. The frontier is built by expanding each vertex's planning state with the successor generator and asking pyrunir which **module rule** (at that vertex's memory state + registers) selects the move, via `pyrunir.kr.ps.ext.SuccessorExpander`: `matching_rule(...)` replays the executor's per-rule applicability (memory match + conditions + effects, DoRule action/argument match) and `apply(...)` returns the resulting proof node, so a taken move also reports the **module + resulting memory** it lands in.

Because the generated successors are off-graph (no proof vertex), `source`/`target` are **planning-state ids** (`sK`) like base. For a taken move, `module`/`memory` give the resulting memory location; a gap leaves `rule`/`module`/`memory` blank:

```text
[successors]
source|action|target|rule|module|memory|flags|delta
s10|a5|s20|r1|M0|m2|GOAL|f0:2>1 f1:1>0
s10|a6|s21||||DEADEND|f1:0>1

[states]
id|flags|hstar|hlmcut|f0|f1
s20|GOAL|0|0|1|0
s21|DEADEND|inf|inf|2|1

[facts]
state|atoms
s20|p0,p1
s21|p0
```

As in base, the `[successors]` rows are followed by a `[states]` table (`hstar`, `hlmcut`, plus the full feature vector of each successor target, state-indexed) and a `[facts]` table (its `fluent`/`derived` atoms). A move that progresses with an empty `rule` is the gap — no module rule selects it. (Load/Call rules are internal memory steps and never select a planning move, so they never appear as a successor's `rule`.)

## Section reference

| Section | Columns | Notes |
|---|---|---|
| `[state]` | `vertex\|state\|module\|memory\|flags\|hstar\|hlmcut\|f0\|f1\|…` | Single witness vertex; `vertex` is `vK`, `state` is `sK`, `module` is `MK`, `memory` is `mK`; `hstar` is shortest remaining plan length for the planning state, `inf` for proven deadends, empty if inconclusive; `hlmcut` is the LM-cut admissible lower bound for the same planning state. |
| `[states]` | `vertex\|state\|module\|memory\|flags\|hstar\|hlmcut\|f0\|f1\|…` | Vertices, wide; `hstar` and `hlmcut` follow the same semantics as `[state]`; feature column order from `features.*`. |
| `[transitions]` | `step\|source\|target\|rule\|action\|delta` | `source`/`target` are **vertex** ids (`vK`); `rule` is `rK` (module rule). |
| `[facts]` | `state\|atoms` | Keyed by **planning state** (`sK`, shared across vertices); `pK` list of fluent/derived atoms. |
| `[cycle]` | `key\|value` | `cycle_vertex_indices` (`vK`) and `cycle_state_indices` (`sK`). |
| `[successors]` | `source\|action\|target\|rule\|module\|memory\|flags\|delta` | Off-graph: `source`/`target` are planning states (`sK`); `module`/`memory` are the resulting memory of a taken move (blank for a gap). |

`fK`/`rK`/`aK`/`pK`/`mK` aliases resolve against the run-global [dictionaries](#dictionaries). `hstar` and `hlmcut` are literal values and are not interned. The `flags` vocabulary is the [same as base](runir.ps.base.counterexamples.md#section-reference).
