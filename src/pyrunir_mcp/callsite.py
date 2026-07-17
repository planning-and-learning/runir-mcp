from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import overload

import pyrunir_mcp.dumping as _dumping
import pyrunir_mcp.validation as _validation
from pyrunir_mcp.candidates import Classifier, ModuleProgram, Policy
from pyrunir_mcp.context import DomainContext, TaskContext
from pyrunir_mcp.defaults import (
    CLASSIFIER_MISTAKE_LIMIT,
    CLASSIFIER_PROOF_BUDGET,
    PLAN_TRACE_BUDGET,
    STRUCTURAL_TERMINATION_MAX_FEATURES,
    STRUCTURAL_TERMINATION_USE_INCOMPLETE_PREPROCESSING,
)
from pyrunir_mcp.dumping import DumpResult
from pyrunir_mcp.enums import DumpFormat
from pyrunir_mcp.history import ValidationHistory
from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.task_generation import (
    TaskGenerationOptions,
    TaskGenerationResult,
    describe_make_problem,
    get_generator_path,
    task_generation,
)
from pyrunir_mcp.validation import (
    FindModuleProgramSolutionResult,
    FindPolicySolutionResult,
    ProveClassifierResult,
    ProvePolicyTerminationResult,
    ProveTerminationResult,
    SearchBudget,
    ValidationResult,
)


def create_domain_context(domain_file: str | Path) -> DomainContext:
    return _validation.create_domain_context(domain_file)


def create_task_context(
    domain_context: DomainContext, problem_file: str | Path, *, num_threads: int = 1
) -> TaskContext:
    return _validation.create_task_context(domain_context, problem_file, num_threads=num_threads)


def create_policy(domain_context: DomainContext, policy_file: str | Path | None) -> Policy:
    return _validation.create_policy(domain_context, policy_file)


def write_empty_policy(domain_context: DomainContext, policy_file: str | Path) -> Policy:
    return _validation.write_empty_policy(domain_context, policy_file)


def create_module_program(
    domain_context: DomainContext, module_program_file: str | Path | None
) -> ModuleProgram:
    return _validation.create_module_program(domain_context, module_program_file)


def create_classifier(
    domain_context: DomainContext, classifier_file: str | Path | None
) -> Classifier:
    return _validation.create_classifier(domain_context, classifier_file)


@overload
def find_solution(
    context: TaskContext,
    candidate: Policy,
    *,
    classifier: Classifier | None = None,
    universal: bool = False,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    shuffle_choice_points: bool = True,
    search_budget: SearchBudget | None = None,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> FindPolicySolutionResult: ...


@overload
def find_solution(
    context: TaskContext,
    candidate: ModuleProgram,
    *,
    classifier: Classifier | None = None,
    universal: bool = False,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    shuffle_choice_points: bool = True,
    search_budget: SearchBudget | None = None,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> FindModuleProgramSolutionResult: ...


def find_solution(
    context: TaskContext,
    candidate: Policy | ModuleProgram,
    *,
    classifier: Classifier | None = None,
    universal: bool = False,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    shuffle_choice_points: bool = True,
    search_budget: SearchBudget | None = None,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> FindPolicySolutionResult | FindModuleProgramSolutionResult:
    return _validation.find_solution(
        context,
        candidate,
        classifier=classifier,
        universal=universal,
        num_rollouts=num_rollouts,
        random_seed=random_seed,
        random_seed_start=random_seed_start,
        shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
        shuffle_choice_points=shuffle_choice_points,
        search_budget=search_budget,
        plan_trace_budget=plan_trace_budget,
    )


def prove_classifier(
    context: TaskContext,
    classifier: Classifier,
    *,
    search_budget: SearchBudget = CLASSIFIER_PROOF_BUDGET,
    max_mistakes_per_category: int = CLASSIFIER_MISTAKE_LIMIT,
) -> ProveClassifierResult:
    return _validation.prove_classifier(
        context,
        classifier,
        search_budget=search_budget,
        max_mistakes_per_category=max_mistakes_per_category,
    )


@overload
def prove_termination(
    domain_context: DomainContext,
    candidate: Policy,
    *,
    max_features: int = STRUCTURAL_TERMINATION_MAX_FEATURES,
    use_incomplete_preprocessing: bool = (
        STRUCTURAL_TERMINATION_USE_INCOMPLETE_PREPROCESSING
    ),
) -> ProvePolicyTerminationResult:
    ...


@overload
def prove_termination(
    domain_context: DomainContext,
    candidate: ModuleProgram,
    *,
    max_features: int = STRUCTURAL_TERMINATION_MAX_FEATURES,
    use_incomplete_preprocessing: bool = (
        STRUCTURAL_TERMINATION_USE_INCOMPLETE_PREPROCESSING
    ),
) -> ProveTerminationResult:
    ...


def prove_termination(
    domain_context: DomainContext,
    candidate: Policy | ModuleProgram,
    *,
    max_features: int = STRUCTURAL_TERMINATION_MAX_FEATURES,
    use_incomplete_preprocessing: bool = (
        STRUCTURAL_TERMINATION_USE_INCOMPLETE_PREPROCESSING
    ),
) -> ProvePolicyTerminationResult | ProveTerminationResult:
    return _validation.prove_termination(
        domain_context,
        candidate,
        max_features=max_features,
        use_incomplete_preprocessing=use_incomplete_preprocessing,
    )


def dump_result(
    result: ValidationResult | TaskGenerationResult,
    output_dir: str | Path,
    *,
    formats: tuple[DumpFormat, ...] = (DumpFormat.JSON,),
    include_witness_trace: bool = True,
    include_plan_trace: bool = True,
    include_successors: bool = True,
) -> DumpResult:
    return _dumping.dump_result(
        result,
        output_dir,
        formats=formats,
        include_witness_trace=include_witness_trace,
        include_plan_trace=include_plan_trace,
        include_successors=include_successors,
    )


def dump_validation_history(
    history: ValidationHistory,
    output_dir: str | Path,
    *,
    formats: tuple[DumpFormat, ...] = (DumpFormat.JSON,),
) -> DumpResult:
    return _dumping.dump_validation_history(history, output_dir, formats=formats)


def describe_generator(domain_name: str) -> tuple[Path, str]:
    return get_generator_path(domain_name), describe_make_problem(domain_name)


def generate_tasks(
    domain_name: str,
    output_dir: str | Path,
    batch_name: str,
    configs: Sequence[Mapping[str, JsonValue]],
    *,
    allow_invalid: bool = False,
) -> TaskGenerationResult:
    return task_generation(
        TaskGenerationOptions(
            domain_name=domain_name,
            output_dir=Path(output_dir),
            batch_name=batch_name,
            configs=configs,
            allow_invalid=allow_invalid,
        )
    )
