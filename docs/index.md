# pyrunir-mcp Docs

Typed Python API with in-memory domains, task contexts, candidates, observations, and histories. Files are written only through dumping.

## Current Interface

- [Python API](api.md)
- [Contexts](context.md): `create_domain_context(...)`, `create_task_context(...)`
- [Candidates](candidates.md): `create_policy(...)`, `write_empty_policy(...)`, `create_module_program(...)`, `create_classifier(...)`
- [Validation History](history.md): `ValidationHistory`, `HistoryFeedback`
- [Dumping](dumping.md): `dump_result(...)`, `dump_validation_history(...)`, `DumpFormat`
- [Search budgets](api.md#searchbudget): `SearchBudget` for validation and open-state FF plan traces

```python
from pyrunir_mcp import (
    SearchBudget,
    ValidationHistory,
    create_classifier,
    create_domain_context,
    create_module_program,
    create_policy,
    create_task_context,
    dump_result,
    dump_validation_history,
    execute_module_program,
    execute_policy,
    prove_classifier,
    prove_module_program,
    prove_policy,
    write_empty_policy,
)
```

Validation returns typed result objects. Dump only when another process needs files.

## Workflow Reference

Workflow-specific arguments, result shapes, and output tables:

### Base Sketch Policy

- [`runir.ps.base.create_empty_policy`](runir.ps.base.create_empty_policy.md): `create_policy(domain, None)` or `write_empty_policy(domain, path)`
- [`runir.ps.base.reformat_policy`](runir.ps.base.reformat_policy.md): formatting workflow/table notes
- [`runir.ps.base.execute_policy`](runir.ps.base.execute_policy.md): `execute_policy(...)`, optional `dump_result(...)`
- [`runir.ps.base.prove_policy`](runir.ps.base.prove_policy.md): `prove_policy(...)`, optional `dump_result(...)`

### Extended Module Programs

- [`runir.ps.ext.create_empty_module_program`](runir.ps.ext.create_empty_module_program.md): `create_module_program(domain, None)`
- [`runir.ps.ext.reformat_module_program`](runir.ps.ext.reformat_module_program.md): formatting workflow/table notes
- [`runir.ps.ext.reformat_module`](runir.ps.ext.reformat_module.md): formatting workflow/table notes
- [`runir.ps.ext.execute_module_program`](runir.ps.ext.execute_module_program.md): `execute_module_program(...)`, optional `dump_result(...)`
- [`runir.ps.ext.prove_module_program`](runir.ps.ext.prove_module_program.md): `prove_module_program(...)`, optional `dump_result(...)`
- [`runir.ps.ext.prove_termination`](runir.ps.ext.prove_termination.md): structural-termination table notes

### Unsolvability Classifiers

- [`runir.uns.create_empty_classifier`](runir.uns.create_empty_classifier.md): `create_classifier(domain, None)`
- [`runir.uns.reformat_classifier`](runir.uns.reformat_classifier.md): formatting workflow/table notes
- [`runir.uns.prove_classifier`](runir.uns.prove_classifier.md): `prove_classifier(...)`, optional `dump_result(...)`

## Output Tables

- [Table definitions](tables/index.md)
- [Rendering conventions](tables/rendering.md)
- [Index tables](tables/index-tables.md)
- Base sketch-policy counterexamples: [tables](tables/runir.ps.base.counterexamples.md)
- Module-program counterexamples: [tables](tables/runir.ps.ext.counterexamples.md)
- Open-state FF plan trace: [tables](tables/runir.ps.open_state.plan_trace.md)
- Structural termination: [tables](tables/runir.ps.ext.prove_termination.md)
- Unsolvability classifier: [tables](tables/runir.uns.prove_classifier.md)

`docs/AGENT.md` records the output policy: JSON for machine metadata, PSV for LLM-readable artifacts, Markdown for human summaries.
