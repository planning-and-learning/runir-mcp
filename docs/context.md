# Contexts

Contexts are the setup objects for the current Python API. They replace the old pattern of passing
`domain_file`, `problem_file`, and `num_threads` to every tool call.

## `create_domain_context`

```python
domain_context = create_domain_context(domain_file)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_file` | `str | Path` | required | Planning domain PDDL file. The path is resolved to an absolute `Path`. |

Returns a `DomainContext`. It owns the parsed `PlanningDomain`, the reusable parser, and the base
policy, module-program, and classifier repositories for that domain. It also allocates stable IDs
for tasks, candidates, and results created from it.

Relevant fields:

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Domain identifier, currently `domain_000001`. |
| `domain_file` | `Path` | Absolute domain file path. |
| `planning_domain` | `PlanningDomain` | Parsed planning domain object. |
| `base_policy_context` | `BasePolicyContext` | Repository/context for base sketch policies. |
| `module_program_context` | `ModuleProgramContext` | Repository/context for extended module programs. |
| `classifier_context` | `ClassifierContext` | Repository/context for unsolvability classifiers. |

## `create_task_context`

```python
task_context = create_task_context(domain_context, problem_file, num_threads=1)
```

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_context` | `DomainContext` | required | Context returned by `create_domain_context(...)`. |
| `problem_file` | `str | Path` | required | Problem PDDL file. The path is resolved to an absolute `Path`. |
| `num_threads` | `int` | `1` | Worker count used by the underlying execution context. |

Returns a `TaskContext`. It parses the problem once, creates lifted and grounded task search
contexts, and stores both base and extended views used by validation calls.

Relevant fields:

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Stable task ID such as `task_000001`. |
| `index` | `int` | Per-domain task index. |
| `problem_file` | `Path` | Absolute problem file path. |
| `execution_context` | `ExecutionContext` | Shared pytyr/yggdrasil execution context. |
| `base_task` | `LoadedSearchContext` | Ground task view for base sketch execution/proof. |
| `base_lifted_task` | `LoadedLiftedSearchContext` | Lifted task view for base h*/LM-cut evidence. |
| `ext_task` | `LoadedSearchContext` | Ground task view for module-program execution/proof. |
| `ext_lifted_task` | `LoadedLiftedSearchContext` | Lifted task view for module-program h*/LM-cut evidence. |

## Usage

Create one `DomainContext` per domain and reuse it for many tasks/candidates/results:

```python
domain = create_domain_context("domain.pddl")
task_a = create_task_context(domain, "p01.pddl")
task_b = create_task_context(domain, "p02.pddl")
```

Validation calls consume contexts directly:

```python
result = execute_policy(domain, task_a, policy)
```
