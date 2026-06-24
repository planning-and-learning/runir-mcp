from __future__ import annotations

from pathlib import Path
from pyrunir_mcp.json_types import JsonObject

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.ext import ConstructorRepositoryFactory as ExtRepositoryFactory
from pyrunir.kr.ps.ext import Module, ModuleStructuralTerminationResult, RepositoryFactory, parse_module_program, structural_termination
from pytyr.formalism.planning import Parser

from pyrunir_mcp.kr.ps.ext.termination.schemas import ProveTerminationOptions
from pyrunir_mcp.kr.ps.ext.termination.serialize import counterexample_to_data, status_name
from pyrunir_mcp.output.run import RunItem, build_run_envelope
from pyrunir_mcp.output.termination import (
    TerminationDictionaries,
    TerminationEdge,
    TerminationVertex,
    counterexample_document,
)

TOOL_NAME = "runir.ps.ext.prove_termination"


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = ExtRepositoryFactory().create(planning_domain)
    program_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, program_repository


def _module_name(module: Module, index: int) -> str:
    name = str(module.get_name())
    return name or f"module-{index:03d}"


def _vertex(data: JsonObject) -> TerminationVertex:
    return TerminationVertex(
        index=data["index"],
        memory_state=data["memory_state"],
        concepts=data["concepts"],
        booleans=data["booleans"],
        numericals=data["numericals"],
    )


def _edge(data: JsonObject) -> TerminationEdge:
    return TerminationEdge(
        index=data["index"],
        source=data["source"],
        target=data["target"],
        rule=data["rule"],
        numerical_changes=data["numerical_changes"],
    )


def _module_result_metadata(module_name: str, module_result: ModuleStructuralTerminationResult) -> JsonObject:
    return {
        "module": module_name,
        "status": status_name(module_result.status),
        "terminating": bool(module_result.is_terminating()),
    }


def prove_termination(options: ProveTerminationOptions) -> JsonObject:
    domain_path = Path(options.domain_file).resolve()
    module_program_file = Path(options.module_program_file).resolve()
    planning_domain, repository = _repositories(domain_path)
    program = parse_module_program(module_program_file.read_text(encoding="utf-8"), planning_domain, repository)
    modules = list(program.get_modules())
    program_result = structural_termination(program)
    module_results = list(program_result.get_module_results())

    dicts = TerminationDictionaries()
    artifacts: dict[str, object] = {}
    items: list[RunItem] = []
    module_summaries: list[JsonObject] = []
    nonterminating_modules: list[str] = []
    for index, (module, module_result) in enumerate(zip(modules, module_results, strict=True), start=1):
        module_name = _module_name(module, index)
        module_summaries.append(_module_result_metadata(module_name, module_result))
        if module_result.is_terminating():
            continue
        nonterminating_modules.append(module_name)
        counterexample = module_result.get_counterexample()
        if counterexample is None:
            continue
        data = counterexample_to_data(counterexample)
        failure_id = f"structural_termination-{len(items) + 1:03d}"
        name = f"failures/{failure_id}/witness"
        artifacts[name] = counterexample_document(
            header=[
                ("tool", TOOL_NAME),
                ("id", failure_id),
                ("category", "structural_termination"),
                ("status", status_name(module_result.status)),
                ("module", module_name),
            ],
            vertices=[_vertex(vertex) for vertex in data["vertices"]],
            edges=[_edge(edge) for edge in data["edges"]],
            dicts=dicts,
        )
        items.append(RunItem(id=failure_id, category="structural_termination", task=module_name, witness=name))

    return build_run_envelope(
        tool=TOOL_NAME,
        status="success" if program_result.is_terminating() else "failure",
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain_file": domain_path.as_posix(),
            "module_program_file": module_program_file.as_posix(),
            "program_status": status_name(program_result.status),
            "terminating": bool(program_result.is_terminating()),
            "nonterminating_modules": nonterminating_modules,
            "recursive_call_rules": [str(rule).strip() for rule in program_result.get_recursive_call_rules()],
            "modules": module_summaries,
        },
        dictionary_tables=dicts.tables(),
        artifacts=artifacts,
        items=items,
    )
