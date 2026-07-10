from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from pypddl.formalism import ParserOptions
from pyrunir.datasets import GroundTaskSearchContext, LiftedTaskSearchContext
from pytyr.formalism.planning import Parser, PlanningTask
from pytyr.planning.lifted import (
    GroundTaskInstantiationOptions,
    GroundTaskInstantiationStatus,
)
from pytyr.planning.lifted import (
    Task as LiftedTask,
)
from pyyggdrasil.execution import ExecutionContext


class PathTaskParser(Protocol):
    def parse_task(self, task_filepath: Path, parser_options: ParserOptions) -> PlanningTask: ...


def parse_task_file(parser: Parser, problem_path: Path, parser_options: ParserOptions) -> PlanningTask:
    # pytyr's overload stub uses PathLike[Unknown]; this narrows the file-path overload.
    return cast(PathTaskParser, parser).parse_task(problem_path, parser_options)


@dataclass(frozen=True)
class LoadedSearchContext:
    problem_path: Path
    search_context: GroundTaskSearchContext


@dataclass(frozen=True)
class LoadedLiftedSearchContext:
    problem_path: Path
    search_context: LiftedTaskSearchContext


def build_lifted_search_context(
    domain_path: Path,
    problem_path: Path,
    execution_context: ExecutionContext,
) -> LiftedTaskSearchContext:
    parser_options = ParserOptions()
    parser = Parser(domain_path, parser_options)
    formalism_task = parse_task_file(parser, problem_path, parser_options)
    lifted_task = LiftedTask(formalism_task)
    return LiftedTaskSearchContext(lifted_task, execution_context)


def build_ground_search_context(
    domain_path: Path,
    problem_path: Path,
    execution_context: ExecutionContext,
) -> GroundTaskSearchContext:
    parser_options = ParserOptions()
    parser = Parser(domain_path, parser_options)
    formalism_task = parse_task_file(parser, problem_path, parser_options)
    lifted_task = LiftedTask(formalism_task)
    grounded = lifted_task.instantiate_ground_task(
        execution_context, GroundTaskInstantiationOptions()
    )
    if grounded.status != GroundTaskInstantiationStatus.SUCCESS:
        raise RuntimeError(f"Grounding failed for {problem_path}: {grounded.status}")
    return GroundTaskSearchContext(grounded.task, execution_context)


def load_lifted_search_context(
    domain_path: Path,
    problem_path: Path,
    execution_context: ExecutionContext,
) -> LoadedLiftedSearchContext:
    return LoadedLiftedSearchContext(
        problem_path=problem_path,
        search_context=build_lifted_search_context(domain_path, problem_path, execution_context),
    )


def load_grounded_search_context(
    domain_path: Path,
    problem_path: Path,
    execution_context: ExecutionContext,
) -> LoadedSearchContext:
    return LoadedSearchContext(
        problem_path=problem_path,
        search_context=build_ground_search_context(domain_path, problem_path, execution_context),
    )
