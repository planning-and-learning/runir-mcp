# Python API

Typed API for keeping parsing, candidates, validation contexts, observations, and history in memory.

```text
src/pyrunir_mcp/
  context.py     # DomainContext and TaskContext
  candidates.py  # Policy, ModuleProgram, Classifier, CandidateSource
  validation.py  # create/find/prove calls and result/observation types
  history.py            # ValidationHistory and HistoryFeedback
  task_generation.py  # generated PDDL task batches
  dumping.py            # dump boundary
  callsite.py           # public convenience exports
```

Callers own all state. `TaskContext` stores the `DomainContext` that created it. Validation calls do not mutate history; fold returned observations explicitly:

```python
feedback = history.fold(result.observation)
```

`HistoryFeedback` reports repeat failures. Failed observations carry a `FailureFingerprint` when available: validation kind, status, problem file, category (`open_state`, `cycle`, `deadend`, or proof/search status), and witness indices. Without a fingerprint, history compares kind/status/candidate/classifier.

## Typical Flow

```python
from pyrunir_mcp import (
    SearchBudget,
    ValidationHistory,
    create_domain_context,
    create_policy,
    create_task_context,
    dump_validation_history,
    find_solution,
    write_empty_policy,
)

domain = create_domain_context("domain.pddl")
task = create_task_context(domain, "problem.pddl")
policy = create_policy(domain, "policy.txt")
history = ValidationHistory()
result = find_solution(task, policy)
feedback = history.fold(result.observation)

assert feedback.total_observations == len(history.observations)
dump_validation_history(history, "artifacts/history")
write_empty_policy(domain, "empty_policy.formatted.txt")
```

## References

- [Contexts](context.md): `create_domain_context(...)`, `create_task_context(...)`
- [Candidates](candidates.md): policy, module-program, and classifier creation
- [Validation History](history.md): `ValidationHistory.fold(...)`
- [`runir.task_generation`](runir.task_generation.md): generator paths, descriptions, and task generation
- [Dumping](dumping.md): `dump_result(...)`, `dump_validation_history(...)`, formats

## Candidates

- `create_policy(domain, policy_file)` returns `Policy`.
- `create_module_program(domain, module_program_file)` returns `ModuleProgram`.
- `create_classifier(domain, classifier_file)` returns `Classifier`.

Pass `None` for an empty candidate. Use `write_empty_policy(domain, path)` when the canonical empty sketch text must also be written.

## runir.task_generation

- `describe_generator(domain_name)` returns `(generator_path, signature)`.
- `get_generator_path(domain_name)` and `get_generator_domain_path(domain_name)` resolve bundled `pypddl-datasets` resources.
- `generate_tasks(domain_name, output_dir, batch_name, configs, allow_invalid=False)` writes generated domain/problem files and returns `TaskGenerationResult`.

See [`runir.task_generation`](runir.task_generation.md) for generator lookup, result fields, invalid config handling, and output files.

## Validation

- `find_solution(task, policy, classifier=None, universal=False, ...)` returns `FindPolicySolutionResult`.
- `find_solution(task, module_program, classifier=None, universal=False, ...)` returns `FindModuleProgramSolutionResult`.
- `prove_termination(domain, policy_or_module_program, *, max_features=16, use_incomplete_preprocessing=True)`
- `prove_classifier(task, classifier, ...)`

`find_solution(...)` performs seeded greedy rollouts when `universal=False` and one exhaustive search when `universal=True`. In universal mode, `num_rollouts=n` allows at most `n` non-cycle counterexamples, fills unused capacity with successful witness traces, and permits one additional cycle outside that limit. See [`runir.ps.find_solution`](runir.ps.find_solution.md).

Every result includes `kind`, `status`, candidate, `observation`, optional `FailureFingerprint`, and validation-specific payload such as solution evidence, termination proof, or classifier counts.

Structural termination limits each residual memory component to `max_features` relevant
boolean and numerical features. The sound incomplete preprocessing pass is enabled by default;
disable it with `use_incomplete_preprocessing=False` when the complete check must run directly.

## SearchBudget

`SearchBudget(max_num_states, max_time_seconds)` groups a state limit and a wall-clock limit. `None` means that side of the budget is left unconstrained for searches that support optional limits.

`find_solution(...)` takes `search_budget` for native validation and `plan_trace_budget` for optional FF plan traces emitted later by `dump_result(...)` for open-state failures. `search_budget=None` selects `SearchBudget(max_num_states=None, max_time_seconds=None)` in existential mode and `SearchBudget(max_num_states=100_000, max_time_seconds=5.0)` in universal mode. Plan traces default to `SearchBudget(max_num_states=1_000_000, max_time_seconds=10.0)`. Explicit universal budgets must set both fields. `prove_classifier` also accepts `search_budget` and defaults to `SearchBudget(max_num_states=1_000_000, max_time_seconds=None)`.

## Dumping

Validation is in-memory. Dump explicitly:

- `dump_result(result, output_dir, *, include_witness=True, include_witness_trace=True, include_plan_trace=True, include_successors=True)` writes result JSON and requested artifacts; disabling evidence also skips its construction. `include_witness` applies to classifier, solution, and structural-termination witnesses. For solution results, disabling all four flags writes only the failing task to the evidence indexes and skips every evidence dictionary and artifact builder.
- `dump_validation_history(history, output_dir)` writes history JSON.

Typed detail objects stay in memory; strings/files are produced at dump/output boundaries.
