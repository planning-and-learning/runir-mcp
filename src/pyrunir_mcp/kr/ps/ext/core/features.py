from __future__ import annotations

from dataclasses import dataclass

from pyrunir.kr.dl.ext import ConstructorRepository as ExtDLConstructorRepository
from pyrunir.kr.ps.ext import Repository as PolicyRepository
from pytyr.formalism.planning import PlanningDomain



@dataclass(frozen=True)
class ModuleProgramContext:
    planning_domain: PlanningDomain
    module_output_repository: ExtDLConstructorRepository
    policy_repository: PolicyRepository

