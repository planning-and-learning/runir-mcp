from __future__ import annotations

from pathlib import Path

from pypddl.formalism import ParserOptions
from pyrunir.datasets import (
    StateGraphCostMode,
    StateGraphGenerationOptions,
    annotate_ground_state_graph,
    generate_ground_state_graph_result,
)
from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLRepositoryFactory
from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
from pyrunir.kr.uns import RepositoryFactory, classify
from pyrunir.kr.uns.dl import parse_classifier
from pyyggdrasil.execution import ExecutionContext
from pytyr.formalism.planning import Parser
from pytyr.planning import SearchStatus

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.kr.uns.schemas import ProveClassifierOptions
from pyrunir_mcp.kr.uns.serialize import feature_symbols, feature_values, fluent_facts
from pyrunir_mcp.output.classifier import ClassifierRow, counterexamples_table
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.run import RunItem, build_run_envelope
from pyrunir_mcp.planning import build_ground_search_context

TOOL_NAME = "runir.uns.prove_classifier"


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = UnsDLRepositoryFactory().create(planning_domain)
    classifier_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, classifier_repository


def prove_classifier(options: ProveClassifierOptions) -> JsonObject:
    domain_path = Path(options.domain_file).resolve()
    problem_path = Path(options.problem_file).resolve()
    planning_domain, repository = _repositories(domain_path)
    description = Path(options.classifier_file).read_text(encoding="utf-8")
    classifier = parse_classifier(description, planning_domain, repository)
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    ctx = ExecutionContext(1)
    dicts = Dictionaries()

    symbols = feature_symbols(classifier)
    caps = {
        "false_positive": options.max_false_positive_counterexamples,
        "false_negative": options.max_false_negative_counterexamples,
    }
    found = {"false_positive": 0, "false_negative": 0}
    rows: list[ClassifierRow] = []
    items: list[RunItem] = []
    failure_category: str | None = None

    context = build_ground_search_context(domain_path, problem_path, ctx)
    generation_options = StateGraphGenerationOptions()
    generation_options.max_num_states = options.max_num_states
    generation_options.max_time = options.max_time_seconds
    result = generate_ground_state_graph_result(context, generation_options)

    if result.status != SearchStatus.EXHAUSTED:
        failure_category = "resource_limit"
        per_task = {"task": problem_path.name, "status": "resource_limit", "reason": f"state-graph generation: {result.status.name}"}
    else:
        graph = annotate_ground_state_graph(context, result.graph, StateGraphCostMode.UNIT_COST).get_forward_graph()
        unsolvable = 0
        for vertex in graph.get_vertex_indices():
            label = graph.get_vertex_property(vertex)
            actually_solvable = not label.is_unsolvable
            unsolvable += not actually_solvable
            eval_context = GroundEvaluationContext(label.state, builder, denotations)
            predicted_unsolvable = bool(classify(classifier, eval_context))
            if predicted_unsolvable and actually_solvable:
                category = "false_positive"
            elif not predicted_unsolvable and not actually_solvable:
                category = "false_negative"
            else:
                continue
            found[category] += 1
            if found[category] > caps[category]:
                continue
            counterexample_id = f"{category}-{found[category]:03d}"
            rows.append(
                ClassifierRow(
                    id=counterexample_id,
                    category=category,
                    state=int(label.state.get_index()),
                    features=feature_values(classifier, eval_context),
                    fluent=tuple(fluent_facts(label.state)),
                )
            )
            items.append(RunItem(id=counterexample_id, category=category, task=problem_path.name, counterexample="counterexamples"))
        per_task = {
            "task": problem_path.name,
            "status": "correct" if not any(found.values()) else "counterexample",
            "states": graph.get_num_vertices(),
            "unsolvable": unsolvable,
            "false_positive": found["false_positive"],
            "false_negative": found["false_negative"],
        }

    status = "success" if not any(found.values()) and failure_category is None else "failure"
    return build_run_envelope(
        tool=TOOL_NAME,
        status=status,
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain_file": domain_path.as_posix(),
            "problem_file": problem_path.as_posix(),
            "classifier_file": options.classifier_file,
            "max_num_states": options.max_num_states,
            "per_task": per_task,
        },
        dictionary_tables=dicts.tables(),
        artifacts={"counterexamples": counterexamples_table(rows, symbols, dicts)},
        items=items,
        failure_category=failure_category,
    )
