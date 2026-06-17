from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyrunir.datasets import GroundTaskSearchContext
from pytyr.planning import ExecutionContext
from pytyr.formalism.planning import Parser, ParserOptions
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


def load_grounded_search_contexts(
    domain_path: Path,
    problem_dir: Path,
    execution_context: ExecutionContext,
) -> list[LoadedSearchContext]:
    parser_options = ParserOptions()
    parser = Parser(domain_path, parser_options)
    instantiation_options = GroundTaskInstantiationOptions()
    contexts = []

    for problem_path in get_problem_paths(problem_dir):
        formalism_task = parser.parse_task(problem_path, parser_options)
        lifted_task = LiftedTask(formalism_task)
        grounded_result = lifted_task.instantiate_ground_task(execution_context, instantiation_options)

        if grounded_result.status != GroundTaskInstantiationStatus.SUCCESS:
            raise RuntimeError(f"Grounding failed for {problem_path}: {grounded_result.status}")

        search_context = GroundTaskSearchContext(grounded_result.task, execution_context)
        contexts.append(LoadedSearchContext(problem_path=problem_path, search_context=search_context))

    return contexts
