# Output: unsolvability-classifier counterexamples

Output-file format for [`runir.uns.prove_classifier`](../runir.uns.prove_classifier.md).

A counterexample is a single **witness state** where the classifier's prediction disagrees with reachable-state-space ground truth — no transitions, cycles, traces, or successors. Each mistake is one `failures/<id>/` directory (`meta.json` + `witness`, no `trace`/`successors`), indexed by `failures.{psv,md,json}`; the two mistake types are distinguished by the `category` (and the `<id>` prefix).

It uses the same PSV/Markdown/JSON encoding and [conventions](runir.ps.base.counterexamples.md#conventions) as the policy tools, with a reduced schema: classifier features are all boolean.

A classifier predicts whether a state is **unsolvable** (`true`) or **solvable** (`false`). The reported mistakes:

- **`false_positive`** — predicted unsolvable on a state that is actually solvable.
- **`false_negative`** — predicted solvable on a state that is actually unsolvable.

## Dictionaries

Under `dicts/`. No rules, actions, or memory — only features and atoms.

| Alias | File | Columns | Notes |
|---|---|---|---|
| `fK` | `features.*` | `id\|symbol` | Classifier features; all boolean. Ordered, drives the feature columns. |
| `pK` | `atoms.*` | `id\|kind\|atom` | `kind` is `fluent` (the reachable-state facts). |

```text
# dicts/features.psv
id|symbol
f0|b_holding_target
f1|b_at_goal

# dicts/atoms.psv
id|kind|atom
p0|fluent|at(robot roomA)
p1|fluent|holding(ball1)
```

## Failures

`failures.{psv,md,json}` indexes the mistakes (one row each), each pointing into its `failures/<id>/` directory:

```text
id|category|problem|witness
false_negative-001|false_negative|p01.pddl|failures/false_negative-001/witness.psv
false_positive-001|false_positive|p01.pddl|failures/false_positive-001/witness.psv
```

- `category` is the mistake type, which encodes the verdict: `false_positive` = predicted unsolvable on a solvable state, `false_negative` = predicted solvable on an unsolvable state.

## Witness

`failures/<id>/witness.{psv,md,json}` — the single misclassified state, in the same `[state]` + `[facts]` form as the policy tools (features are all boolean):

```text
@tool prove_classifier
@id false_negative-001
@category false_negative

[state]
id|flags|f0|f1
s57|WITNESS|T|F

[facts]
state|atoms
s57|p0,p1
```

- `f0|f1|…` are the boolean classifier features (order from `features.*`) — the input behind the wrong call, i.e. the repair signal.
- `[facts]` carries the state's fluent atoms as a `pK` list.

## Section reference

| Section | Columns | Notes |
|---|---|---|
| `[state]` | `id\|flags\|f0\|f1\|…` | The single misclassified state; `fK` boolean feature columns. |
| `[facts]` | `state\|atoms` | The state's fluent atoms as a `pK` list. |

`fK`/`pK` aliases resolve against the run-global [dictionaries](#dictionaries). The verdict is the `@category` header (and the `<id>` prefix).
