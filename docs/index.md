# pyrunir-mcp Docs

`pyrunir-mcp` now exposes a typed Python API. Consumers hold parsed domains, task contexts,
candidates, validation observations, and histories in memory. Filesystem output is an explicit dump
boundary, not the primary call interface.

## Current Interface

Start with the Python API guide:

- [Python API](api.md)
- [Contexts](context.md): `create_domain_context(...)` and `create_task_context(...)`
- [Candidates](candidates.md): `create_policy(...)`, `write_empty_policy(...)`, `create_module_program(...)`, and `create_classifier(...)`
- [Validation History](history.md): `ValidationHistory` and `HistoryFeedback`
- [Dumping](dumping.md): `dump_result(...)`, `dump_validation_history(...)`, and `DumpFormat`

The current public entry points are grouped across setup, validation, history, and dumping:

```python
from pyrunir_mcp import (
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

Validation functions return typed result objects and do not write files. Use `dump_result(...)` or
`dump_validation_history(...)` when another process needs artifacts on disk.

## Workflow Reference

The pages below are restored from the old per-tool documentation. The old `runir.*` names are now
workflow labels, not the primary call interface. Each page starts with a current Python API mapping
and then preserves the detailed argument/result/output notes from the tool version.

### Base Sketch Policy

- [`runir.ps.base.create_empty_policy`](runir.ps.base.create_empty_policy.md): use `create_policy(domain, None)` or `write_empty_policy(domain, path)`.
- [`runir.ps.base.reformat_policy`](runir.ps.base.reformat_policy.md): legacy formatting workflow; no top-level Python reformat call is currently exported.
- [`runir.ps.base.execute_policy`](runir.ps.base.execute_policy.md): use `execute_policy(...)`, then optionally `dump_result(...)`.
- [`runir.ps.base.prove_policy`](runir.ps.base.prove_policy.md): use `prove_policy(...)`, then optionally `dump_result(...)`.

### Extended Module Programs

- [`runir.ps.ext.create_empty_module_program`](runir.ps.ext.create_empty_module_program.md): use `create_module_program(domain, None)`.
- [`runir.ps.ext.reformat_module_program`](runir.ps.ext.reformat_module_program.md): legacy formatting workflow; no top-level Python reformat call is currently exported.
- [`runir.ps.ext.reformat_module`](runir.ps.ext.reformat_module.md): legacy formatting workflow; no top-level Python reformat call is currently exported.
- [`runir.ps.ext.execute_module_program`](runir.ps.ext.execute_module_program.md): use `execute_module_program(...)`, then optionally `dump_result(...)`.
- [`runir.ps.ext.prove_module_program`](runir.ps.ext.prove_module_program.md): use `prove_module_program(...)`, then optionally `dump_result(...)`.
- [`runir.ps.ext.prove_termination`](runir.ps.ext.prove_termination.md): legacy structural-termination workflow; no top-level Python call is currently exported.

### Unsolvability Classifiers

- [`runir.uns.create_empty_classifier`](runir.uns.create_empty_classifier.md): use `create_classifier(domain, None)`.
- [`runir.uns.reformat_classifier`](runir.uns.reformat_classifier.md): legacy formatting workflow; no top-level Python reformat call is currently exported.
- [`runir.uns.prove_classifier`](runir.uns.prove_classifier.md): use `prove_classifier(...)`, then optionally `dump_result(...)`.

## Output File Formats

The detailed artifact format docs remain useful when calling `dump_result(...)` with PSV, Markdown,
or JSON formats:

- Base sketch-policy counterexamples: [base output format](output/runir.ps.base.counterexamples.md).
- Module-program counterexamples: [module-program output format](output/runir.ps.ext.counterexamples.md).
- Structural termination: [termination output format](output/runir.ps.ext.prove_termination.md)
  (historical reference; no current public dump path emits it).
- Unsolvability classifier: [classifier output format](output/runir.uns.prove_classifier.md)
  (historical reference; current `dump_result(...)` writes `result.json` only for
  `prove_classifier(...)`).

`docs/AGENT.md` records the output policy: JSON for machine metadata, PSV for LLM-readable
artifacts, and Markdown for human summaries.
