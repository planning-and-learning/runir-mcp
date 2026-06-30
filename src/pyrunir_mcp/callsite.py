from __future__ import annotations

from pathlib import Path

from pyrunir_mcp.candidates import Classifier, ModuleProgram, Policy
from pyrunir_mcp.context import DomainContext, TaskContext
from pyrunir_mcp.dumping import DumpFormat, DumpResult
from pyrunir_mcp.history import ValidationHistory
from pyrunir_mcp.validation import (
    ExecuteModuleProgramResult,
    ExecutePolicyResult,
    ProveClassifierResult,
    ProveModuleProgramResult,
    ProvePolicyResult,
    ValidationResult,
)
import pyrunir_mcp.dumping as _dumping
import pyrunir_mcp.validation as _validation


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


def execute_policy(
    domain_context: DomainContext,
    context: TaskContext,
    policy: Policy,
    *,
    classifier: Classifier | None = None,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    max_arity: int = 0,
    max_num_states: int | None = None,
    max_time_seconds: float | None = None,
) -> ExecutePolicyResult:
    return _validation.execute_policy(
        domain_context,
        context,
        policy,
        classifier=classifier,
        num_rollouts=num_rollouts,
        random_seed=random_seed,
        random_seed_start=random_seed_start,
        shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
        max_arity=max_arity,
        max_num_states=max_num_states,
        max_time_seconds=max_time_seconds,
    )


def execute_module_program(
    domain_context: DomainContext,
    context: TaskContext,
    module_program: ModuleProgram,
    *,
    classifier: Classifier | None = None,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    max_arity: int = 0,
    max_num_states: int | None = None,
    max_time_seconds: float | None = None,
) -> ExecuteModuleProgramResult:
    return _validation.execute_module_program(
        domain_context,
        context,
        module_program,
        classifier=classifier,
        num_rollouts=num_rollouts,
        random_seed=random_seed,
        random_seed_start=random_seed_start,
        shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
        max_arity=max_arity,
        max_num_states=max_num_states,
        max_time_seconds=max_time_seconds,
    )


def prove_policy(
    domain_context: DomainContext,
    context: TaskContext,
    policy: Policy,
    *,
    classifier: Classifier | None = None,
    max_num_states: int = 100_000,
    max_time_seconds: float = 5.0,
) -> ProvePolicyResult:
    return _validation.prove_policy(
        domain_context,
        context,
        policy,
        classifier=classifier,
        max_num_states=max_num_states,
        max_time_seconds=max_time_seconds,
    )


def prove_module_program(
    domain_context: DomainContext,
    context: TaskContext,
    module_program: ModuleProgram,
    *,
    classifier: Classifier | None = None,
    max_num_states: int = 100_000,
    max_time_seconds: float = 5.0,
    max_arity: int = 0,
) -> ProveModuleProgramResult:
    return _validation.prove_module_program(
        domain_context,
        context,
        module_program,
        classifier=classifier,
        max_num_states=max_num_states,
        max_time_seconds=max_time_seconds,
        max_arity=max_arity,
    )


def prove_classifier(
    domain_context: DomainContext,
    context: TaskContext,
    classifier: Classifier,
    *,
    max_num_states: int = 1_000_000,
    max_time_seconds: float = 1_000_000_000.0,
) -> ProveClassifierResult:
    return _validation.prove_classifier(
        domain_context,
        context,
        classifier,
        max_num_states=max_num_states,
        max_time_seconds=max_time_seconds,
    )


def dump_result(
    result: ValidationResult,
    output_dir: str | Path,
    *,
    formats: tuple[DumpFormat, ...] = (DumpFormat.JSON,),
) -> DumpResult:
    return _dumping.dump_result(result, output_dir, formats=formats)


def dump_validation_history(
    history: ValidationHistory,
    output_dir: str | Path,
    *,
    formats: tuple[DumpFormat, ...] = (DumpFormat.JSON,),
) -> DumpResult:
    return _dumping.dump_validation_history(history, output_dir, formats=formats)
