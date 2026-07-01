# Python API

Typed API for keeping parsing, candidates, validation contexts, observations, and history in memory.

```text
src/pyrunir_mcp/
  context.py     # DomainContext and TaskContext
  candidates.py  # Policy, ModuleProgram, Classifier, CandidateSource
  validation.py  # create/execute/prove calls and result/observation types
  history.py     # ValidationHistory and HistoryFeedback
  dumping.py     # dump boundary
  callsite.py    # public convenience exports
```

Callers own all state. `TaskContext` stores the `DomainContext` that created it. Validation calls do not mutate history; fold returned observations explicitly:

```python
feedback = history.fold(result.observation)
```

`HistoryFeedback` reports repeat failures. Failed observations carry a `FailureFingerprint` when available: validation kind, status, problem file, category (`open_state`, `cycle`, `deadend`, `deadend_transition`, or proof/search status), and witness indices. Without a fingerprint, history compares kind/status/candidate/classifier.

## Typical Flow

```python
from pyrunir_mcp import (
    SearchBudget,
    ValidationHistory,
    create_domain_context,
    create_policy,
    create_task_context,
    dump_validation_history,
    execute_policy,
    write_empty_policy,
)

domain = create_domain_context("domain.pddl")
task = create_task_context(domain, "problem.pddl")
policy = create_policy(domain, "policy.txt")
history = ValidationHistory()
result = execute_policy(task, policy)
feedback = history.fold(result.observation)

assert feedback.total_observations == len(history.observations)
dump_validation_history(history, "artifacts/history")
write_empty_policy(domain, "empty_policy.formatted.txt")
```

## References

- [Contexts](context.md): `create_domain_context(...)`, `create_task_context(...)`
- [Candidates](candidates.md): policy, module-program, and classifier creation
- [Validation History](history.md): `ValidationHistory.fold(...)`
- [Dumping](dumping.md): `dump_result(...)`, `dump_validation_history(...)`, formats

## Candidates

- `create_policy(domain, policy_file)` returns `Policy`.
- `create_module_program(domain, module_program_file)` returns `ModuleProgram`.
- `create_classifier(domain, classifier_file)` returns `Classifier`.

Pass `None` for an empty candidate. Use `write_empty_policy(domain, path)` when the canonical empty sketch text must also be written.

## Validation

- `execute_policy(task, policy, classifier=None, ...)`
- `prove_policy(task, policy, classifier=None, ...)`
- `execute_module_program(task, module_program, classifier=None, ...)`
- `prove_module_program(task, module_program, classifier=None, ...)`
- `prove_classifier(task, classifier, ...)`

Every result includes `kind`, `status`, candidate, `observation`, optional `FailureFingerprint`, and validation-specific payload such as failure, proof, or classifier counts.

## SearchBudget

`SearchBudget(max_num_states, max_time_seconds)` groups a state limit and a wall-clock limit. `None` means that side of the budget is left unconstrained for searches that support optional limits.

Policy/module-program execute and prove calls take two budgets: `search_budget` for the validation search itself, and `plan_trace_budget` for optional FF plan traces emitted later by `dump_result(...)` for open-state failures. Execute defaults to `SearchBudget(max_num_states=None, max_time_seconds=None)`, prove defaults to `SearchBudget(max_num_states=100_000, max_time_seconds=5.0)`, and plan traces default to `SearchBudget(max_num_states=1_000_000, max_time_seconds=10.0)`. Prove `search_budget` values must set both fields.

## Dumping

Validation is in-memory. Dump explicitly:

- `dump_result(result, output_dir)` writes result JSON and requested artifacts.
- `dump_validation_history(history, output_dir)` writes history JSON.

Typed detail objects stay in memory; strings/files are produced at dump/output boundaries.
