# Output: unsolvability-classifier counterexamples

Output-file format for [`runir.uns.prove_classifier`](../runir.uns.prove_classifier.md).

A counterexample is a single **witness state** where the classifier's prediction disagrees with reachable-state-space ground truth — no transitions, cycles, traces, or successors. Because every witness is just one state, the whole result is **one flat table**, `counterexamples.{psv,md,json}`, with one row per mistake. Both mistake types live in the same table, distinguished by a `category` column; splitting `false_positive`/`false_negative` into separate tables would only partition rows of identical schema.

It uses the same PSV/Markdown/JSON encoding and [conventions](runir.ps.base.counterexamples.md#conventions) as the policy tools, with a reduced schema: classifier features are all boolean.

A classifier predicts whether a state is **unsolvable** (`true`) or **solvable** (`false`). The reported mistakes:

- **`false_positive`** — predicted unsolvable on a state that is actually solvable.
- **`false_negative`** — predicted solvable on a state that is actually unsolvable.

## Dictionaries

No rules, actions, or memory — only features and atoms.

| Alias | File | Columns | Notes |
|---|---|---|---|
| `fK` | `features.*` | `id\|symbol` | Classifier features; all boolean. Ordered, drives the feature columns. |
| `pK` | `atoms.*` | `id\|kind\|atom` | `kind` is `fluent` (the reachable-state facts). |

```text
# features.psv
id|symbol
f0|b_holding_target
f1|b_at_goal

# atoms.psv
id|kind|atom
p0|fluent|at(robot roomA)
p1|fluent|holding(ball1)
```

## Counterexamples

`counterexamples.{psv,md,json}` — one row per witness state, both categories merged:

```text
id|category|state|f0|f1|atoms
false_negative-001|false_negative|57|T|F|p0,p1
false_positive-001|false_positive|12|F|T|p3,p4
```

- `category` is the mistake type, which encodes the verdict: `false_positive` = predicted unsolvable on a solvable state, `false_negative` = predicted solvable on an unsolvable state.
- `state` is the planning state index.
- `f0|f1|…` are the boolean classifier features (order from `features.*`) — the input behind the wrong call, i.e. the repair signal.
- `atoms` is the state's fluent atoms as a `pK` list.

If fact sets get large, `atoms` can move to a companion `state|atoms` table instead of the inline column; default is inline.

## Section reference

| Section | Columns | Notes |
|---|---|---|
| `counterexamples` | `id\|category\|state\|f0\|f1\|…\|atoms` | One row per witness; both categories merged via `category`; `fK` boolean feature columns; `atoms` a `pK` list. |

`fK`/`pK` aliases resolve against the run-global dictionaries above. There is no `flags` column and no per-state `[facts]` section — the verdict is the `category` column and facts are the inline `atoms` column.
