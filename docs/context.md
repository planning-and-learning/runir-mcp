# Contexts

Contexts keep parsed domain/task state reusable across validation calls.

## `create_domain_context`

```python
domain_context = create_domain_context(domain_file)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_file` | `str | Path` | required | Planning domain PDDL file; resolved to an absolute `Path`. |

Returns a `DomainContext`: parsed `PlanningDomain`, reusable parser, domain repositories, and stable ID counters for tasks, candidates, and results.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Domain identifier, currently `domain_000001`. |
| `domain_file` | `Path` | Absolute domain file path. |
| `planning_domain` | `PlanningDomain` | Parsed planning domain object. |
| `base_policy_context` | `BasePolicyContext` | Base sketch-policy repository/context. |
| `module_program_context` | `ModuleProgramContext` | Extended module-program repository/context. |
| `classifier_context` | `ClassifierContext` | Unsolvability-classifier repository/context. |

## `create_task_context`

```python
task_context = create_task_context(domain_context, problem_file, num_threads=1)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Parent domain context. |
| `problem_file` | `str | Path` | required | Problem PDDL file; resolved to an absolute `Path`. |
| `num_threads` | `int` | `1` | Underlying execution-context worker count. |

Returns a `TaskContext`: parent `DomainContext`, parsed problem, lifted/grounded search contexts, and base/extended task views. Validation derives domain state from `task_context.domain_context`.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Stable task ID such as `task_000001`. |
| `domain_context` | `DomainContext` | Parent domain context. |
| `index` | `int` | Per-domain task index. |
| `problem_file` | `Path` | Absolute problem file path. |
| `execution_context` | `ExecutionContext` | Shared pytyr/yggdrasil execution context. |
| `base_task` | `LoadedSearchContext` | Ground task view for base sketch execution/proof. |
| `base_lifted_task` | `LoadedLiftedSearchContext` | Lifted task view for base h*/LM-cut evidence. |
| `ext_task` | `LoadedSearchContext` | Ground task view for module-program execution/proof. |
| `ext_lifted_task` | `LoadedLiftedSearchContext` | Lifted task view for module-program h*/LM-cut evidence. |

The base and extended ground views share one `LoadedSearchContext`, which owns one native
`GroundTaskContext`. Its `search_context`, `dl_builder`, and `dl_denotation_repository` are
reused by execution, proof, classifier, frontier, evidence, dump, and plan-trace evaluation
for the lifetime of the task context. The dataset `GroundTaskSearchContext` does not own
description-logic resources.
These mutable semantic resources are used sequentially within one task context; parallel work
uses distinct task contexts.

```python
domain = create_domain_context("domain.pddl")
task_a = create_task_context(domain, "p01.pddl")
result = execute_policy(task_a, policy)
```
