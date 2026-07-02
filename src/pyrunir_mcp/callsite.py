from __future__ import annotations

from pathlib import Path

from pyrunir_mcp.candidates import Classifier, ModuleProgram, Policy
from pyrunir_mcp.context import DomainContext, TaskContext
from pyrunir_mcp.dumping import DumpFormat, DumpResult
from pyrunir_mcp.history import ValidationHistory
from pyrunir_mcp.defaults import (
    CLASSIFIER_MISTAKE_LIMIT,
    CLASSIFIER_PROOF_BUDGET,
    EXECUTE_SEARCH_BUDGET,
    PLAN_TRACE_BUDGET,
    PROVE_SEARCH_BUDGET,
)
from pyrunir_mcp.validation import (
    ExecuteModuleProgramResult,
    ExecutePolicyResult,
    ProveClassifierResult,
    ProveModuleProgramResult,
    ProvePolicyResult,
    ProveTerminationResult,
    SearchBudget,
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
    context: TaskContext,
    policy: Policy,
    *,
    classifier: Classifier | None = None,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    max_arity: int = 0,
    search_budget: SearchBudget = EXECUTE_SEARCH_BUDGET,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ExecutePolicyResult:
    return _validation.execute_policy(
        context,
        policy,
        classifier=classifier,
        num_rollouts=num_rollouts,
        random_seed=random_seed,
        random_seed_start=random_seed_start,
        shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
        max_arity=max_arity,
        search_budget=search_budget,
        plan_trace_budget=plan_trace_budget,
    )


def execute_module_program(
    context: TaskContext,
    module_program: ModuleProgram,
    *,
    classifier: Classifier | None = None,
    num_rollouts: int = 1,
    random_seed: int = 0,
    random_seed_start: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    max_arity: int = 0,
    search_budget: SearchBudget = EXECUTE_SEARCH_BUDGET,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ExecuteModuleProgramResult:
    return _validation.execute_module_program(
        context,
        module_program,
        classifier=classifier,
        num_rollouts=num_rollouts,
        random_seed=random_seed,
        random_seed_start=random_seed_start,
        shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
        max_arity=max_arity,
        search_budget=search_budget,
        plan_trace_budget=plan_trace_budget,
    )


def prove_policy(
    context: TaskContext,
    policy: Policy,
    *,
    evidence_classifier: Classifier | None = None,
    search_budget: SearchBudget = PROVE_SEARCH_BUDGET,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
) -> ProvePolicyResult:
    return _validation.prove_policy(
        context,
        policy,
        evidence_classifier=evidence_classifier,
        search_budget=search_budget,
        plan_trace_budget=plan_trace_budget,
    )


def prove_module_program(
    context: TaskContext,
    module_program: ModuleProgram,
    *,
    evidence_classifier: Classifier | None = None,
    search_budget: SearchBudget = PROVE_SEARCH_BUDGET,
    plan_trace_budget: SearchBudget = PLAN_TRACE_BUDGET,
    max_arity: int = 0,
) -> ProveModuleProgramResult:
    return _validation.prove_module_program(
        context,
        module_program,
        evidence_classifier=evidence_classifier,
        search_budget=search_budget,
        plan_trace_budget=plan_trace_budget,
        max_arity=max_arity,
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


def prove_termination(
    domain_context: DomainContext,
    module_program: ModuleProgram,
) -> ProveTerminationResult:
    return _validation.prove_termination(domain_context, module_program)


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
