# pyrunir-mcp

`pyrunir-mcp` is a typed Python API for planning-and-learning agents. Callers keep domains, tasks, candidates, validation results, and history in memory; filesystem artifacts are written only at the dump boundary.

See [`docs/api.md`](docs/api.md) for the API and [`docs/index.md`](docs/index.md) for workflow/output tables.

## Basic Flow

```python
from pyrunir_mcp import (
    ValidationHistory,
    create_domain_context,
    create_policy,
    create_task_context,
    dump_result,
    find_solution,
    generate_tasks,
)

domain = create_domain_context("domain.pddl")
task = create_task_context(domain, "problem.pddl")
policy = create_policy(domain, "policy.txt")
history = ValidationHistory()

result = find_solution(task, policy)
feedback = history.fold(result.observation)
dump_result(result, "artifacts/find-solution")
```

## Entry Points

Context/candidates:

- `create_domain_context(domain_file)`
- `create_task_context(domain_context, problem_file, num_threads=1)`
- `create_policy(domain_context, policy_file)`; pass `None` for an empty policy
- `write_empty_policy(domain_context, policy_file)` for canonical empty policy text
- `create_module_program(domain_context, module_program_file)`; pass `None` for the built-in empty module program
- `create_classifier(domain_context, classifier_file)`; pass `None` for an empty classifier

`runir.task_generation`:

- `describe_generator(domain_name)`
- `get_generator_path(domain_name)` / `get_generator_domain_path(domain_name)`
- `generate_tasks(domain_name, output_dir, batch_name, configs, allow_invalid=False)`

Validation:

- `find_solution(task_context, policy_or_module_program, classifier=None, universal=False, ...)`
- `prove_termination(domain_context, policy_or_module_program, ...)`
- `prove_classifier(task_context, classifier, ...)`

Dumping:

- `dump_result(result, output_dir, formats=(DumpFormat.JSON,))`
- `dump_validation_history(history, output_dir, formats=(DumpFormat.JSON,))`

`DumpFormat.PSV`, `DumpFormat.MD`, and `DumpFormat.JSON` request LLM-readable PSV, human-readable Markdown, and machine-readable JSON. Validation calls do not write files.
