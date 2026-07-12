from __future__ import annotations

import importlib.util
import inspect
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import FunctionType, ModuleType

from pyrunir_mcp.artifacts import fresh_output_dir
from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.keys import (
    Keys,
)

_BATCH_NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")
_GENERATORS_PACKAGE = "pypddl_datasets.generators.classical"
WORKFLOW_NAME = "runir.task_generation"


def batch_slug(batch_name: str) -> str:
    return _BATCH_NAME_RE.sub("_", str(batch_name)).strip("_") or "batch"


def generator_root() -> Path:
    return Path(str(resources.files(_GENERATORS_PACKAGE))).resolve()


@dataclass(frozen=True, slots=True)
class GeneratedTask:
    index: int
    path: Path
    config: JsonObject


@dataclass(frozen=True, slots=True)
class InvalidTaskGenerationConfig:
    index: int
    config: JsonObject
    reason: str
    error_type: str = "Error"
    error_category: str = "invalid_config"


@dataclass(frozen=True, slots=True)
class TaskGenerationOptions:
    domain_name: str
    output_dir: Path
    batch_name: str
    configs: Sequence[Mapping[str, JsonValue]]
    allow_invalid: bool = False


@dataclass(frozen=True, slots=True)
class TaskGenerationResult:
    domain_path: Path
    problem_dir: Path
    generator_path: Path
    signature: str
    generated: list[GeneratedTask]
    invalid: list[InvalidTaskGenerationConfig]

    @property
    def is_successful(self) -> bool:
        return not self.invalid

    @property
    def status(self) -> str:
        return "success" if self.is_successful else "failure"


def get_generator_path(domain_name: str) -> Path:
    if not domain_name.isidentifier():
        raise ValueError(f"Invalid generator domain name: {domain_name!r}")
    return generator_root() / domain_name / "generator.py"


def get_generator_domain_path(domain_name: str) -> Path:
    return get_generator_path(domain_name).with_name("domain.pddl")


def load_generator_module(domain_name: str) -> ModuleType:
    generator_path = get_generator_path(domain_name)
    if not generator_path.exists():
        raise FileNotFoundError(f"Generator not found: {generator_path}")

    module_name = f"_pyrunir_mcp_generator_{domain_name}"
    spec = importlib.util.spec_from_file_location(module_name, generator_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import generator from {generator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_make_problem(domain_name: str) -> FunctionType:
    module = load_generator_module(domain_name)
    make_problem = module.make_problem
    if not isinstance(make_problem, FunctionType):
        raise TypeError(
            f"{get_generator_path(domain_name)} defines make_problem as {type(make_problem).__name__}, expected function"
        )
    return make_problem


def _generator_signature(make_problem: FunctionType) -> str:
    return str(inspect.signature(make_problem))


def _call_generator(make_problem: FunctionType, config: Mapping[str, JsonValue]) -> str:
    result = make_problem(**dict(config))
    if result is None:
        raise ValueError("make_problem returned None")
    if not isinstance(result, str):
        raise TypeError(f"make_problem returned {type(result).__name__}, expected str")
    return result


def describe_make_problem(domain_name: str) -> str:
    return _generator_signature(load_make_problem(domain_name))


def task_generation_json(result: TaskGenerationResult) -> JsonObject:
    generated: list[JsonValue] = [
        {
            Keys.INDEX: item.index,
            Keys.TASK_PATH: item.path.resolve().as_posix(),
            Keys.CONFIG: item.config,
        }
        for item in result.generated
    ]
    invalid: list[JsonValue] = [
        {
            Keys.INDEX: item.index,
            Keys.CONFIG: item.config,
            Keys.REASON: item.reason,
            Keys.ERROR_TYPE: item.error_type,
            Keys.ERROR_CATEGORY: item.error_category,
        }
        for item in result.invalid
    ]
    return {
        Keys.SCHEMA_VERSION: 1,
        Keys.TOOL: WORKFLOW_NAME,
        Keys.STATUS: result.status,
        Keys.DOMAIN_PATH: result.domain_path.as_posix(),
        Keys.TASK_DIR: result.problem_dir.as_posix(),
        Keys.GENERATOR_PATH: result.generator_path.as_posix(),
        Keys.SIGNATURE: result.signature,
        Keys.GENERATED_TASKS: generated,
        Keys.INVALID_TASKS: invalid,
    }


def write_task_generation_markdown(path: Path, result: TaskGenerationResult) -> None:
    lines = [
        "# runir.task_generation",
        "",
        f"Status: `{result.status}`",
        "",
        "## Counts",
        "",
        f"- Generated: {len(result.generated)}",
        f"- Invalid: {len(result.invalid)}",
        "",
        "## Generated Problems",
        "",
    ]
    if not result.generated:
        lines.append("No generated problems.")
    for item in result.generated:
        lines.append(f"- `{item.path.name}`: `{item.path.resolve().as_posix()}`")
    if result.invalid:
        lines.extend(["", "## Invalid Configs", ""])
        for item in result.invalid:
            lines.append(f"- index {item.index}: {item.reason}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _reserve_problem_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return path.is_dir() and not any(path.iterdir())
    return True


def fresh_problem_dir(output_dir: Path, batch_name: str) -> Path:
    slug = batch_slug(batch_name)
    problem_dir = output_dir / slug
    if _reserve_problem_dir(problem_dir):
        return problem_dir
    for index in range(2, 10000):
        candidate = output_dir / f"{slug}-{index:03d}"
        if _reserve_problem_dir(candidate):
            return candidate
    raise RuntimeError(f"could not allocate fresh sample batch directory under {output_dir}")


def task_generation(options: TaskGenerationOptions) -> TaskGenerationResult:
    make_problem = load_make_problem(options.domain_name)
    signature = _generator_signature(make_problem)
    generator_path = get_generator_path(options.domain_name)
    source_domain_path = get_generator_domain_path(options.domain_name)
    if not source_domain_path.exists():
        raise FileNotFoundError(f"Generator domain not found: {source_domain_path}")

    output_dir = fresh_output_dir(options.output_dir)
    slug = batch_slug(options.batch_name)
    problem_dir = fresh_problem_dir(output_dir, slug)

    domain_path = output_dir / "domain.pddl"
    with source_domain_path.open("rb") as source, domain_path.open("xb") as target:
        shutil.copyfileobj(source, target)

    generated: list[GeneratedTask] = []
    invalid: list[InvalidTaskGenerationConfig] = []

    for index, config in enumerate(options.configs, start=1):
        config_dict = dict(config)
        try:
            problem = _call_generator(make_problem, config_dict)
        except Exception as exc:  # noqa: BLE001 - report generator feedback to the outer loop.
            invalid_config = InvalidTaskGenerationConfig(
                index=index,
                config=config_dict,
                reason=str(exc),
                error_type=type(exc).__name__,
                error_category="invalid_config"
                if isinstance(exc, TypeError | ValueError)
                else "generator_error",
            )
            invalid.append(invalid_config)
            if options.allow_invalid:
                continue
            break

        problem_path = problem_dir / f"{slug}-{index:03d}.pddl"
        with problem_path.open("x", encoding="utf-8") as fh:
            fh.write(problem)
        generated.append(GeneratedTask(index=index, path=problem_path, config=config_dict))

    metadata_path = problem_dir / "configs.json"
    metadata = {
        Keys.DOMAIN_NAME: options.domain_name,
        Keys.GENERATOR_PATH: str(generator_path),
        Keys.SIGNATURE: signature,
        Keys.GENERATED_TASKS: [
            {
                Keys.INDEX: problem.index,
                Keys.TASK_PATH: problem.path.resolve().as_posix(),
                Keys.CONFIG: problem.config,
            }
            for problem in generated
        ],
        Keys.INVALID_TASKS: [
            {
                Keys.INDEX: item.index,
                Keys.CONFIG: item.config,
                Keys.REASON: item.reason,
                Keys.ERROR_TYPE: item.error_type,
                Keys.ERROR_CATEGORY: item.error_category,
            }
            for item in invalid
        ],
    }
    with metadata_path.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    return TaskGenerationResult(
        domain_path=domain_path,
        problem_dir=problem_dir,
        generator_path=generator_path,
        signature=signature,
        generated=generated,
        invalid=invalid,
    )
