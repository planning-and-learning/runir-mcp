# runir.task_generation

`runir.task_generation` is a caller-managed Python workflow for creating PDDL task batches from benchmark generators. It imports a generator, writes generated domain/problem files, and returns a typed `TaskGenerationResult` that callers can inspect before optionally dumping summaries.

## Generator Lookup

Generators and their domains are loaded from `pypddl-datasets==0.0.5` package resources:

```text
pypddl_datasets/generators/classical/<domain_name>/generator.py
```

Each generator directory must contain:

- `generator.py` with a callable `make_problem(...)` function.
- `domain.pddl`, copied into the task-generation output directory.

## `describe_generator`

```python
from pyrunir_mcp import describe_generator, get_generator_domain_path

generator_path, signature = describe_generator("gripper")
domain_path = get_generator_domain_path("gripper")
```

Returns the resolved generator source path and the Python signature of `make_problem(...)`. This does not create output files.

## `generate_tasks`

```python
from pyrunir_mcp import DumpFormat, dump_result, generate_tasks

result = generate_tasks(
    "gripper",
    "artifacts/gripper-samples",
    "train",
    configs=[
        {"num_balls": 1},
        {"num_balls": 2},
    ],
)

if result.is_successful:
    problems = [item.path for item in result.generated]

dump = dump_result(result, result.domain_path.parent, formats=(DumpFormat.JSON, DumpFormat.MD))
```

Arguments:

| Name | Type | Default | Description |
|---|---|---|---|
| `domain_name` | `str` | required | Generator directory name under `generators/classical`. |
| `output_dir` | `str | Path` | required | Directory for generated files. Existing output is preserved by allocating a `run-NNN` child. |
| `batch_name` | `str` | required | Problem batch directory and filename prefix. Unsafe characters are replaced with `_`. |
| `configs` | `Sequence[Mapping[str, JsonValue]]` | required | Keyword arguments passed to `make_problem(...)`. |
| `allow_invalid` | `bool` | `False` | Continue after invalid configs instead of stopping at the first invalid config. |

`make_problem(**config)` must return a PDDL problem string. `None` or non-string returns are reported as invalid configs.

## Result

`generate_tasks(...)` returns `TaskGenerationResult`.

| Field | Type | Description |
|---|---|---|
| `domain_path` | `Path` | Copied domain file in the output directory. |
| `problem_dir` | `Path` | Directory containing generated problems and `configs.json`. |
| `generator_path` | `Path` | Source generator path. |
| `signature` | `str` | `make_problem(...)` signature. |
| `generated` | `list[GeneratedTask]` | Generated problem metadata. |
| `invalid` | `list[InvalidTaskGenerationConfig]` | Invalid config diagnostics. |
| `is_successful` | `bool` | `True` when no invalid configs were reported. |
| `status` | `str` | `"success"` or `"failure"`. |

`GeneratedTask` contains `index`, `path`, and `config`.

`InvalidTaskGenerationConfig` contains `index`, `config`, `reason`, `error_type`, and `error_category`.

## Files

Generation writes:

```text
<output_dir>/
  .pyrunir-mcp-output
  domain.pddl
  <batch_slug>/
    <batch_slug>-001.pddl
    <batch_slug>-002.pddl
    configs.json
```

`configs.json` records `generated_tasks` and `invalid_tasks` config metadata. Calling `dump_result(...)` can also write:

```text
<output_dir>/result.json
<output_dir>/summary.md
```

`DumpFormat.JSON` writes `result.json`; `DumpFormat.MD` writes `summary.md`.
