# Output: base sketch-policy counterexamples, traces, and successors

Shared output-file format for the base sketch-policy tools — [`runir.ps.base.execute_policy`](../runir.ps.base.execute_policy.md) and [`runir.ps.base.prove_policy`](../runir.ps.base.prove_policy.md). Both write the same alias dictionaries and counterexample/trace/successor files described here. Each tool's own index/summary layer (execute's `failures`/`manifest`, prove's `summary`) and tool-specific options live in that tool's doc.

Each structured artifact is built once as a logical table — or, for the sectioned witness/trace/successor files, a document of `@key value` headers plus named tables — and rendered through the shared renderer (`pyrunir_mcp.tables`) into the same data in three forms:

- **`.psv`** — compact **pipe-delimited** text, the canonical LLM-facing format: minimal tokens, unambiguous columns.
- **`.md`** — the same tables as aligned Markdown, for reading by eye.
- **`.json`** — the same tables as JSON records, for machine consumption.

While we are still settling on the best representation, all three are emitted so they can be compared directly; the set is controlled by a `formats` option that later narrows to `["psv"]`. The conventions below describe the `.psv` rendering — the `.md` and `.json` files are mechanical renders of the same logical tables (see [The same tables in Markdown and JSON](#the-same-tables-in-markdown-and-json)).

## Conventions

- **Tables** are pipe-separated with a single header row naming the columns. No alignment padding, no Markdown rule (`|---|`) row. Cells are joined by `|` with no surrounding spaces.
- A `|` never appears inside a cell. Ground actions, atoms, feature names, and feature deltas contain no `|`.
- Cells never contain newlines; multi-line action strings are reduced to their first line.
- **Header lines** carry scalar metadata as `@key value`, one per line, before any table. The value is the opaque remainder of the line. Each tool adds its own keys (e.g. `execute_policy` adds `@seed`).
- Boolean values render as `T`/`F`, numeric values as integers.
- An empty optional value renders as an empty cell.
- **Interning via run-global dictionaries.** Features, rules, actions, and atoms recur across every trace and counterexample in a run (these tools run a single problem, so the ground actions/atoms are shared too). Each is listed **once per run** in a top-level dictionary file and referenced everywhere by a short alias `<prefix><K>`. This bounds each value to one full occurrence per run, independent of trace count, trace length, or symbol size:
  - **Features → `fK`** — `features.*` (`id|symbol`; often long DL expressions). Used as `[state]`/`[states]` columns (`idx|flags|f0|f1|…`) and as `delta` keys (`fK:before>after`).
  - **Rules → `rK`** — `rules.*` (`id|symbol`). Used in the `[transitions]` `rule` column.
  - **Actions → `aK`** — `actions.*` (`id|action`). Used in the `[transitions]` `action` column.
  - **Atoms → `pK`** — `atoms.*` (`id|kind|atom`, `kind` is `fluent`, `derived`, or `static`). Fluent/derived atoms are listed per state in `[facts]` as a comma-separated `pK` list. `static` atoms hold in every state, so they appear once in `atoms.*` and are never repeated in `[facts]`.

  The alias is the `id` column of its dictionary file. Trace/counterexample files therefore carry no `@features`/`@rules`/`@actions` headers or `[atoms]` section — they reference the global dictionaries directly.

## Dictionaries

Four run-global files, each a single table mapping an alias `id` to its value. Every trace/counterexample references these aliases. Written in all three formats like the other artifacts.

`features.*` is **ordered**, and that order is load-bearing: the row sequence defines the `f0,f1,…` indices and therefore the exact left-to-right column order of every `[state]`/`[states]` table. (`rules.*`, `actions.*`, `atoms.*` are likewise indexed by row order, but only `features.*` drives a column layout.)

```text
# features.psv
id|symbol
f0|n_undeliv
f1|n_held
f2|b_atgoal

# rules.psv
id|symbol
r0|pickup_r1
r1|deliver_r2

# actions.psv
id|action
a0|(pickup ball1 roomA)
a1|(drop ball1 roomB)

# atoms.psv
id|kind|atom
p0|fluent|at(robot roomA)
p1|fluent|holding(ball1)
p2|derived|clear(roomB)
p3|static|adjacent(roomA roomB)
p4|static|ball(ball1)
```

## Counterexamples

Files `counterexamples/<category>/<id>.{psv,md,json}` — the witness, a single state or a cycle. Scalar header lines carry metadata; sections carry the witness. Feature/rule/action/atom values appear as aliases that resolve against the run-global [dictionaries](#dictionaries).

```text
@tool execute_policy
@id cycle-001
@category cycle
@status CYCLE
@problem p01.pddl
```

**State witness** (non-cycle categories) — one `[state]` section plus its facts:

```text
[state]
idx|flags|f0|f1|f2
42|WITNESS|3|0|F

[facts]
state|atoms
42|p0,p1,p2
```

**Cycle witness** — a `[cycle]` descriptor plus the states and transitions on the cycle:

```text
[cycle]
key|value
cycle_state_indices|1,2,1
cycle_transition_steps|0,1

[states]
idx|flags|f0|f1|f2
1|CYCLE|2|1|F
2|CYCLE|2|0|F

[transitions]
step|src|tgt|rule|action|delta
0|1|2|r1|a1|f1:1>0
1|2|1|r0|a0|f1:0>1

[facts]
state|atoms
1|p1
2|p0
```

## Traces

Files `traces/<category>/<id>.{psv,md,json}` — the path from the initial state to the witness. Same header convention, with `[states]`, `[transitions]`, and `[facts]` sections. There is no separate `chosen_actions` list — it is the `action` column of `[transitions]`.

```text
@tool execute_policy
@id cycle-001
@category cycle
@status CYCLE
@problem p01.pddl

[states]
idx|flags|f0|f1|f2
0|INIT|3|0|F
1||2|1|F
2|CYCLE|2|0|F

[transitions]
step|src|tgt|rule|action|delta
0|0|1|r0|a0|f1:0>1
1|1|2|r1|a1|f0:3>2 f1:1>0

[facts]
state|atoms
0|p0
1|p1
```

## Successors

Files `successors/<category>/<id>.{psv,md,json}` — the 1-step frontier of moves the policy *could* take, the signal for **what is missing to make progress**: each row is an available move with its feature change (`delta`) and whether any sketch rule selects it (`rule`). A move that advances toward the goal with an **empty `rule` cell** is the gap — no rule picks the progressing move.

The frontier is built by **expanding every state along the trace/cycle with the planning successor generator** and marking each generated transition with the sketch rule that selects it (`rule`), or empty when none does. (The proof/execution graph holds only sketch-compatible transitions, so it can't surface the moves the policy *failed* to take — the generator can.) The `src` column is the state each successor branches from; with several trace states, rows for each appear under their own `src`.

Emitted for `open_state`, `cycle`, and `deadend` (named `deadend_transition` in proof). For the common case where the policy is stuck immediately (an initial open state), the trace is a single state and the frontier is exactly that state's applicable moves — all with an empty `rule` when no rule fires.

```text
@tool execute_policy
@id open_state-001
@category open_state
@problem p01.pddl

[successors]
src|action|tgt|rule|flags|delta
0|a0|0|||
0|a1|1||GOAL|f0:2>1 f2:F>T
0|a2|2|r1||f1:0>1

[states]
idx|flags|f0|f1|f2
0||2|1|F
1|GOAL|1|0|T
2||2|0|F
```

Here move `a1` reaches a goal but has an empty `rule` — the missing guidance — while `a2` is the only move a rule (`r1`) selects. The full 1-step frontier is always emitted (never truncated — a missing move is exactly what this artifact is for). `[states]` carries the full feature vector of each successor (the absolute values behind each `delta`); a `GOAL` flag marks successors that satisfy the goal (`DEADEND` is not computed for off-graph successors).

## The same tables in Markdown and JSON

The `.md` and `.json` files carry the identical data, rendered from the same logical tables. For the `[transitions]` section shown above:

Markdown (`.md`) — columns padded to align:

```text
| step | src | tgt | rule | action | delta         |
| ---- | --- | --- | ---- | ------ | ------------- |
| 0    | 0   | 1   | r0   | a0     | f1:0>1        |
| 1    | 1   | 2   | r1   | a1     | f0:3>2 f1:1>0 |
```

JSON (`.json`) — one record per row, native types:

```json
[
  {"step": 0, "src": 0, "tgt": 1, "rule": "r0", "action": "a0", "delta": "f1:0>1"},
  {"step": 1, "src": 1, "tgt": 2, "rule": "r1", "action": "a1", "delta": "f0:3>2 f1:1>0"}
]
```

In the `.json` file the whole sectioned document is one object with the header isolated under its own key: `{"header": {…}, "sections": {"states": [...], "transitions": [...], …}}`. Booleans stay `true`/`false` in JSON (rendered `T`/`F` only in `.psv` and `.md`).

## Section reference

| Section | Columns | Notes |
|---|---|---|
| `[state]` | `idx\|flags\|f0\|f1\|…` | Single witness state; one `fK` feature column (alias order from `features.*`). |
| `[states]` | `idx\|flags\|f0\|f1\|…` | Feature vectors, wide; one `fK` feature column (alias order from `features.*`). |
| `[transitions]` | `step\|src\|tgt\|rule\|action\|delta` | `src`/`tgt` are state indices; `rule` is `rK`, `action` is `aK`; `delta` is space-separated `fK:before>after`, changed features only. |
| `[facts]` | `state\|atoms` | `atoms` is a comma-separated `pK` list referencing `atoms.*`; lists only the per-state `fluent`/`derived` atoms. `static` atoms hold everywhere and are not repeated here. |
| `[cycle]` | `key\|value` | Cycle descriptor: state-index path and transition steps. |
| `[successors]` | `src\|action\|tgt\|rule\|flags\|delta` | 1-step successor frontier branching from `src`, expanded with the planning successor generator for every state along the trace/cycle. `rule` is the sketch rule that selects the move, empty when none does (the gap). |

All `fK`/`rK`/`aK`/`pK` aliases resolve against the run-global [dictionaries](#dictionaries).

The `flags` column holds a comma-separated set of state markers, empty when nothing notable applies (an unremarkable, alive state) or the status was not evaluated. `GOAL`/`DEADEND` are the status exceptions worth flagging:

| Flag | Meaning |
|---|---|
| `INIT` | Initial state. |
| `GOAL` | Goal state. |
| `OPEN` | Open / unexpanded state (e.g. an `open_state` witness). |
| `WITNESS` | The counterexample witness state. |
| `CYCLE` | State participating in the cycle. |
| `DEADEND` | Dead — the goal is unreachable from this state. |
