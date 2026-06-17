from __future__ import annotations

from pathlib import Path
from typing import Any

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtRepositoryFactory
from pyrunir.kr.ps.ext import RepositoryFactory, parse_module_program, structural_termination
from pytyr.formalism.planning import Parser

from pyrunir_mcp.artifacts import write_native_counterexample_run
from pyrunir_mcp.kr.ps.ext.termination.schemas import ProveTerminationOptions
from pyrunir_mcp.kr.ps.ext.termination.serialize import counterexample_to_data, status_name

TOOL_NAME = "runir.ps.ext.prove_termination"


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = ExtRepositoryFactory().create(planning_domain)
    program_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, program_repository


def _module_name(module: object, index: int) -> str:
    get_name = getattr(module, "get_name", None)
    if callable(get_name):
        return str(get_name())
    return f"module-{index:03d}"


def _module_result_metadata(module_name: str, module_result: object) -> dict[str, Any]:
    return {
        "module": module_name,
        "status": status_name(module_result.status),
        "terminating": bool(module_result.is_terminating()),
    }


def prove_termination(options: ProveTerminationOptions) -> dict[str, Any]:
    domain_path = Path(options.domain).resolve()
    module_program_file = Path(options.module_program_file).resolve()
    planning_domain, repository = _repositories(domain_path)
    program = parse_module_program(module_program_file.read_text(encoding="utf-8"), planning_domain, repository)
    modules = list(program.get_modules())
    program_result = structural_termination(program)
    module_results = list(program_result.get_module_results())

    counterexamples: list[dict[str, Any]] = []
    module_summaries: list[dict[str, Any]] = []
    for index, (module, module_result) in enumerate(zip(modules, module_results, strict=True), start=1):
        module_name = _module_name(module, index)
        module_summaries.append(_module_result_metadata(module_name, module_result))
        if module_result.is_terminating():
            continue
        counterexample = module_result.get_counterexample()
        if counterexample is None:
            continue
        counterexamples.append(
            {
                "category": "structural_termination",
                "module": module_name,
                "task": module_name,
                "status": status_name(module_result.status),
                "counterexample": counterexample_to_data(counterexample),
            }
        )

    return write_native_counterexample_run(
        tool=TOOL_NAME,
        status="success" if program_result.is_terminating() else "failure",
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain": domain_path.as_posix(),
            "module_program_file": module_program_file.as_posix(),
            "program_status": status_name(program_result.status),
            "terminating": bool(program_result.is_terminating()),
            "recursive_call_rules": [
                str(rule).strip() for rule in program_result.get_recursive_call_rules()
            ],
            "modules": module_summaries,
        },
        counterexamples=counterexamples,
    )
