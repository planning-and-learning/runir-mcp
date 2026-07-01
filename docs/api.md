# Python API

The validation API is the typed Python surface for callers that want to keep parsing,
candidate objects, validation contexts, and history in memory.

The API is split into top-level modules by responsibility:

```text
src/pyrunir_mcp/
  context.py     # DomainContext and TaskContext
  candidates.py  # Policy, ModuleProgram, Classifier, and CandidateSource
  validation.py  # create/execute/prove calls plus validation result and observation types
  history.py     # externally owned ValidationHistory and HistoryFeedback
  dumping.py     # explicit result/history dump boundary
  callsite.py    # thin convenience exports for public call functions
```

Callers own the state explicitly. `DomainContext`, `TaskContext`, and `ValidationHistory` are normal
Python objects held by the caller; runir-mcp does not store them globally. Validation calls do not
mutate history. They return a `ValidationObservation`, which caller code can fold into its own
`ValidationHistory` with:

```python
feedback = history.fold(result.observation)
```

`fold` returns `HistoryFeedback`, including whether the same validation failure fingerprint has
appeared before. Failed observations carry a `FailureFingerprint` when runir-mcp can identify a
concrete failure: validation kind, status, problem file, category (`open_state`, `cycle`, `deadend`,
`deadend_transition`, or a proof/search status), and witness vertex/edge/cycle indices. If no
fingerprint is available, history falls back to the older validation kind/status/candidate/classifier
key. This gives learning loops immediate feedback while still keeping the state externally managed
by the caller.

## Typical Flow

```python
from pyrunir_mcp import (
    create_domain_context,
    create_task_context,
    create_policy,
    execute_policy,
    dump_validation_history,
    ValidationHistory,
    write_empty_policy,
)

domain = create_domain_context("domain.pddl")
task = create_task_context(domain, "problem.pddl")
policy = create_policy(domain, "policy.txt")
history = ValidationHistory()
result = execute_policy(domain, task, policy)
feedback = history.fold(result.observation)

assert feedback.total_observations == len(history.observations)
dump_validation_history(history, "artifacts/history")
write_empty_policy(domain, "empty_policy.formatted.txt")
```

## Setup References

- [Contexts](context.md) documents `create_domain_context(...)` and `create_task_context(...)`.
- [Candidates](candidates.md) documents policy, module-program, and classifier creation.
- [Validation History](history.md) documents `ValidationHistory.fold(...)`.
- [Dumping](dumping.md) documents `dump_result(...)`, `dump_validation_history(...)`, and formats.

## Candidate Creation

- `create_policy(domain, policy_file)` returns `Policy`.
- `create_module_program(domain, module_program_file)` returns `ModuleProgram`.
- `create_classifier(domain, classifier_file)` returns `Classifier`.

Passing `None` creates the corresponding empty candidate. Use `write_empty_policy(domain, path)` when a caller also needs Runir's canonical textual empty sketch written to disk for agent workspaces or parser checks.

## Validation Calls

- `execute_policy(domain, task, policy, classifier=None, ...)`
- `prove_policy(domain, task, policy, classifier=None, ...)`
- `execute_module_program(domain, task, module_program, classifier=None, ...)`
- `prove_module_program(domain, task, module_program, classifier=None, ...)`
- `prove_classifier(domain, task, classifier, ...)`

Every validation result includes:

- typed `kind: ValidationKind`;
- typed `status: ValidationStatus`;
- typed candidate object;
- typed `observation: ValidationObservation` that callers may fold into externally owned history;
- optional `FailureFingerprint` on failed observations for repeat-failure detection;
- validation-family-specific payload such as failure, proof, or classifier counts.

## Dump Boundary

Validation calls do not write artifacts directly. Dumping is explicit:

- `dump_result(result, output_dir)` writes result JSON.
- `dump_validation_history(history, output_dir)` writes history JSON.

In memory, observations keep typed detail objects (`ExecuteObservationDetails`,
`ProofObservationDetails`, `ClassifierObservationDetails`) and typed fingerprints. Strings are
produced only at dump/output boundaries.
