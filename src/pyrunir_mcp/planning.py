from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir.datasets import GroundTaskSearchContext
from pypddl.formalism import ParserOptions
from pytyr.formalism.planning import Parser
from pyyggdrasil.execution import ExecutionContext
from pytyr.planning.lifted import (
    GroundTaskInstantiationOptions,
    GroundTaskInstantiationStatus,
    Task as LiftedTask,
)


@dataclass(frozen=True)
class LoadedSearchContext:
    problem_path: Path
    search_context: GroundTaskSearchContext


def get_problem_paths(problem_dir: Path) -> list[Path]:
    return sorted(path for path in problem_dir.glob("*.pddl") if path.name != "domain.pddl")


def build_ground_search_context(
    domain_path: Path,
    problem_path: Path,
    execution_context: ExecutionContext,
) -> GroundTaskSearchContext:
    parser_options = ParserOptions()
    parser = Parser(domain_path, parser_options)
    formalism_task = parser.parse_task(problem_path, parser_options)
    lifted_task = LiftedTask(formalism_task)
    grounded = lifted_task.instantiate_ground_task(
        execution_context, GroundTaskInstantiationOptions()
    )
    if grounded.status != GroundTaskInstantiationStatus.SUCCESS:
        raise RuntimeError(f"Grounding failed for {problem_path}: {grounded.status}")
    return GroundTaskSearchContext(grounded.task, execution_context)


def load_grounded_search_context(
    domain_path: Path,
    problem_path: Path,
    execution_context: ExecutionContext,
) -> LoadedSearchContext:
    return LoadedSearchContext(
        problem_path=problem_path,
        search_context=build_ground_search_context(domain_path, problem_path, execution_context),
    )


def load_grounded_search_contexts(
    domain_path: Path,
    problem_dir: Path,
    execution_context: ExecutionContext,
) -> list[LoadedSearchContext]:
    return [
        load_grounded_search_context(domain_path, problem_path, execution_context)
        for problem_path in get_problem_paths(problem_dir)
    ]
