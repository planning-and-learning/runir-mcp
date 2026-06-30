# pyrunir-mcp

`pyrunir-mcp` exposes a typed Python API for planning-and-learning agents.
Callers keep domains, tasks, candidates, validation results, and validation history in memory, and
write filesystem artifacts only at the explicit dump boundary.

The current Python API is documented in [`docs/api.md`](docs/api.md). The detailed historical
per-tool pages are restored under [`docs/index.md`](docs/index.md) as workflow/output reference
material; they describe the same validation families and artifact formats using their old tool
names.

## Basic Flow

```python
from pyrunir_mcp import (
    ValidationHistory,
    create_domain_context,
    create_policy,
    create_task_context,
    dump_result,
    execute_policy,
)

domain = create_domain_context("domain.pddl")
task = create_task_context(domain, "problem.pddl")
policy = create_policy(domain, "policy.txt")
history = ValidationHistory()

result = execute_policy(domain, task, policy)
feedback = history.fold(result.observation)
dump_result(result, "artifacts/execute-policy")
```

## Current Python Entry Points

Context and candidates:

- `create_domain_context(domain_file)`
- `create_task_context(domain_context, problem_file, num_threads=1)`
- `create_policy(domain_context, policy_file)`; pass `None` for an empty policy
- `write_empty_policy(domain_context, policy_file)` to write Runir's canonical empty policy text
- `create_module_program(domain_context, module_program_file)`; pass `None` for the built-in empty module program
- `create_classifier(domain_context, classifier_file)`; pass `None` for an empty classifier

Validation:

- `execute_policy(domain_context, task_context, policy, classifier=None, ...)`
- `prove_policy(domain_context, task_context, policy, classifier=None, ...)`
- `execute_module_program(domain_context, task_context, module_program, classifier=None, ...)`
- `prove_module_program(domain_context, task_context, module_program, classifier=None, ...)`
- `prove_classifier(domain_context, task_context, classifier, ...)`

Dumping:

- `dump_result(result, output_dir, formats=(DumpFormat.JSON,))`
- `dump_validation_history(history, output_dir, formats=(DumpFormat.JSON,))`

Use `DumpFormat.PSV`, `DumpFormat.MD`, and `DumpFormat.JSON` to request LLM-readable PSV,
human-readable Markdown, and machine-readable JSON artifacts. Validation calls themselves do not
write output files.

## Detailed Workflow and Output Docs

[`docs/index.md`](docs/index.md) restores the detailed workflow pages and output contracts for the
restored `runir.*` workflow names. In the current interface, read those names as workflow labels:
`runir.ps.base.execute_policy` maps to `execute_policy(...)`,
`runir.ps.base.prove_policy` maps to `prove_policy(...)`, and so on. The output-format pages remain
relevant for artifacts produced by `dump_result(..., formats=(DumpFormat.PSV, DumpFormat.MD,
DumpFormat.JSON))`.
