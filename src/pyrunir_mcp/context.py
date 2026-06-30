from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyyggdrasil.execution import ExecutionContext
from pytyr.formalism.planning import Parser, PlanningDomain

from pyrunir_mcp.kr.ps.base.core.data_loader import (
    LoadedLiftedSearchContext as BaseLoadedLiftedSearchContext,
)
from pyrunir_mcp.kr.ps.base.core.data_loader import LoadedSearchContext as BaseLoadedSearchContext
from pyrunir_mcp.kr.ps.base.core.features import BasePolicyContext
from pyrunir_mcp.kr.ps.ext.core.data_loader import (
    LoadedLiftedSearchContext as ExtLoadedLiftedSearchContext,
)
from pyrunir_mcp.kr.ps.ext.core.data_loader import LoadedSearchContext as ExtLoadedSearchContext
from pyrunir_mcp.kr.ps.ext.core.features import ModuleProgramContext
from pyrunir_mcp.kr.ps.classifier import ClassifierContext


@dataclass(slots=True)
class DomainContext:
    id: str
    domain_file: Path
    parser: Parser
    planning_domain: PlanningDomain
    base_policy_context: BasePolicyContext
    module_program_context: ModuleProgramContext
    classifier_context: ClassifierContext
    next_task_index: int = 1
    next_policy_index: int = 1
    next_module_program_index: int = 1
    next_classifier_index: int = 1
    next_result_index: int = 1


@dataclass(slots=True)
class TaskContext:
    id: str
    index: int
    problem_file: Path
    execution_context: ExecutionContext
    base_task: BaseLoadedSearchContext
    base_lifted_task: BaseLoadedLiftedSearchContext
    ext_task: ExtLoadedSearchContext
    ext_lifted_task: ExtLoadedLiftedSearchContext
