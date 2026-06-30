# pyrunir-mcp

`pyrunir-mcp` now exposes a Python API for planning-and-learning agents.
Callers keep domain contexts, task contexts, candidates, validation results, and validation history
in memory, and explicitly dump results only when they need filesystem artifacts.

The Python API is documented in [`docs/api.md`](docs/api.md).

## Basic Flow

```python
from pyrunir_mcp import (
    ValidationHistory,
    create_task_context,
    create_domain_context,
    create_policy,
    execute_policy,
)

domain = create_domain_context("domain.pddl")
task = create_task_context(domain, "problem.pddl")
policy = create_policy(domain, "policy.txt")
history = ValidationHistory()

result = execute_policy(domain, task, policy)
feedback = history.fold(result.observation)
```

Use `dump_result(...)` and `dump_validation_history(...)` when an external process needs files.
The old file-path based MCP tools and invoke CLI have been removed; consumers should depend on the
Python API directly.
