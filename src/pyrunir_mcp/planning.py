from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

from pypddl.formalism import ParserOptions
from pyrunir.datasets import GroundTaskSearchContext, LiftedTaskSearchContext
from pyrunir.kr import GroundTaskContext
from pyrunir.kr.ps.base import Sketch
from pyrunir.kr.ps.base.dl import parse_sketch
from pyrunir.kr.ps.ext import ModuleProgram as RunirModuleProgram
from pyrunir.kr.ps.ext.dl import parse_module_program
from pyrunir.kr.uns import Classifier as RunirClassifier
from pyrunir.kr.uns.dl import parse_classifier
from pytyr.formalism.planning import Parser, PlanningDomain, PlanningTask
from pytyr.planning.lifted import (
    GroundTaskInstantiationOptions,
    GroundTaskInstantiationStatus,
)
from pytyr.planning.lifted import (
    Task as LiftedTask,
)
from pyyggdrasil.execution import ExecutionContext

from pyrunir_mcp.candidates import Classifier, ModuleProgram, Policy


class PathTaskParser(Protocol):
    def parse_task(self, task_filepath: Path, parser_options: ParserOptions) -> PlanningTask: ...


def parse_task_file(parser: Parser, problem_path: Path, parser_options: ParserOptions) -> PlanningTask:
    # pytyr's overload stub uses PathLike[Unknown]; this narrows the file-path overload.
    return cast(PathTaskParser, parser).parse_task(problem_path, parser_options)


@dataclass(frozen=True)
class LoadedSearchContext:
    problem_path: Path
    task_context: GroundTaskContext
    _policies: dict[str, tuple[Policy, Sketch]] = field(
        default_factory=lambda: dict[str, tuple[Policy, Sketch]](),
        init=False,
        repr=False,
        compare=False,
    )
    _module_programs: dict[str, tuple[ModuleProgram, RunirModuleProgram]] = field(
        default_factory=lambda: dict[str, tuple[ModuleProgram, RunirModuleProgram]](),
        init=False,
        repr=False,
        compare=False,
    )
    _classifiers: dict[str, tuple[Classifier, RunirClassifier]] = field(
        default_factory=lambda: dict[str, tuple[Classifier, RunirClassifier]](),
        init=False,
        repr=False,
        compare=False,
    )

    @property
    def search_context(self) -> GroundTaskSearchContext:
        return self.task_context.search_context

    def get_policy(self, planning_domain: PlanningDomain, policy: Policy) -> Sketch:
        cached = self._policies.get(policy.id)
        if cached is not None and cached[0] is policy:
            return cached[1]
        value = parse_sketch(
            str(policy.value), planning_domain, self.task_context.base_repository
        )
        self._policies[policy.id] = (policy, value)
        return value

    def get_module_program(
        self, planning_domain: PlanningDomain, module_program: ModuleProgram
    ) -> RunirModuleProgram:
        cached = self._module_programs.get(module_program.id)
        if cached is not None and cached[0] is module_program:
            return cached[1]
        value = parse_module_program(
            str(module_program.value), planning_domain, self.task_context.ext_repository
        )
        self._module_programs[module_program.id] = (module_program, value)
        return value

    def get_classifier(
        self, planning_domain: PlanningDomain, classifier: Classifier
    ) -> RunirClassifier:
        cached = self._classifiers.get(classifier.id)
        if cached is not None and cached[0] is classifier:
            return cached[1]
        value = parse_classifier(
            str(classifier.value), planning_domain, self.task_context.uns_repository
        )
        self._classifiers[classifier.id] = (classifier, value)
        return value


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
        task_context=GroundTaskContext(
            build_ground_search_context(domain_path, problem_path, execution_context)
        ),
    )
