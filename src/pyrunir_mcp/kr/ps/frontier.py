"""Successor-frontier expansion for policy witnesses (base sketch + ext module program).

The proof/execution graph holds only policy-compatible transitions, so a stuck (open) state
has no out-edges there and the graph cannot surface the moves a policy *failed* to take. To
expose the full 1-step frontier — every applicable move and which rule (if any) selects it —
we expand each state on the witness trace with the pytyr successor generator and mark compatibility
with the policy:

- base: `Sketch.is_compatible_with(GroundEvaluationContext(source, target))`;
- ext:  `pyrunir.kr.ps.ext.SuccessorExpander`, whose context-based methods replay the
  module-program executor's per-rule applicability at the vertex's memory state + registers and
  return the resulting proof node so each taken move can report the module + memory it lands in.

A successor that advances toward the goal with an empty `rule` is the gap. Successors are
off-graph planning moves (no proof vertex), so they are emitted state-indexed; ext additionally
carries source and target module/memory context per taken move (see `proof.witness_artifacts`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from pyrunir.kr import GroundTaskContext
from pyrunir.kr.ps.base import GroundSketchProofGraph, Sketch
from pyrunir.kr.ps.base.dl import GroundEvaluationContext
from pyrunir.kr.ps.ext import (
    GroundSuccessorExpander,
    GroundModuleProgramProofGraph,
    ModuleProgram,
)
from pytyr.formalism.planning import GroundAction
from pytyr.planning.ground import ConjunctiveGoalStrategy, Node, State

from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.keys import (
    Keys,
)
from pyrunir_mcp.kr.ps.feature_evidence import FeatureEvidence
from pyrunir_mcp.output.policy import Successor
from pyrunir_mcp.output.proof_witness import successor as build_successor

# Expand the deduped witness-trace/cycle vertices of a proof graph into their 1-step successor frontier.
ProofGraph: TypeAlias = GroundSketchProofGraph | GroundModuleProgramProofGraph
FrontierExpander: TypeAlias = Callable[[ProofGraph, list[int]], list[Successor]]


def format_ground_action(action: GroundAction) -> str:
    inner = action.get_action()
    arguments = ", ".join(str(obj) for obj in action.get_objects())
    return f"{inner.get_name()}({arguments})"


def goal_test(task_context: GroundTaskContext) -> Callable[[State], bool]:
    goal = ConjunctiveGoalStrategy(task_context.search_context.task)
    seed_state = task_context.search_context.state_repository.get_initial_state()

    def is_goal(state: State) -> bool:
        try:
            return bool(goal.is_dynamic_goal_satisfied(seed_state, state))
        except RuntimeError:
            return False

    return is_goal


def successor(
    source_state: State,
    target_state: State,
    action: GroundAction,
    rule: str | None,
    evidence: FeatureEvidence,
    is_goal: Callable[[State], bool],
    *,
    module: str | None = None,
    memory: str | None = None,
    source_memory: tuple[str, str] | None = None,
) -> Successor:
    source = {Keys.STATE_INDEX: int(source_state.get_index()), **evidence(source_state)}
    if source_memory is not None:
        source[Keys.MODULE], source[Keys.MEMORY] = source_memory
    target = {Keys.STATE_INDEX: int(target_state.get_index()), Keys.IS_GOAL: is_goal(target_state), **evidence(target_state)}
    if module is not None:
        target[Keys.MODULE] = module
        target[Keys.MEMORY] = memory
    edge: JsonObject = {Keys.ACTION: format_ground_action(action), Keys.RULE: rule}
    return build_successor(source, edge, target)


def make_frontier_expander(
    task_context: GroundTaskContext,
    sketch: Sketch,
    evidence: FeatureEvidence,
) -> FrontierExpander:
    """Base sketch: every 1-step successor of each witness-trace vertex's state, tagged with the sketch
    rule that selects it (empty = the gap)."""
    generator = task_context.search_context.successor_generator
    rules = list(sketch.get_rules())
    builder = task_context.dl_builder
    denotations = task_context.dl_denotation_repository
    is_goal = goal_test(task_context)

    def compatible_rule(source_state: State, target_state: State) -> str | None:
        context = GroundEvaluationContext(source_state, target_state, builder, denotations)
        if not sketch.is_compatible_with(context):
            return None
        for rule in rules:
            if rule.is_compatible_with(context):
                return str(rule.get_symbol()).strip()
        return "<sketch-compatible>"

    def expand(graph: ProofGraph, vertices: list[int]) -> list[Successor]:
        if not isinstance(graph, GroundSketchProofGraph):
            return []
        successors: list[Successor] = []
        for vertex in vertices:
            source_state = graph.get_vertex_property(int(vertex)).state
            for labeled in generator.get_labeled_successor_nodes(Node(source_state, 0.0)):
                target_state = labeled.node.get_state()
                rule = compatible_rule(source_state, target_state)
                successors.append(successor(source_state, target_state, labeled.label, rule, evidence, is_goal))
        return successors

    return expand


def make_ext_frontier_expander(
    task_context: GroundTaskContext,
    program: ModuleProgram,
    evidence: FeatureEvidence,
) -> FrontierExpander:
    """Module program: every 1-step successor of each witness-trace vertex's state, tagged with the module
    rule (at the vertex's memory state + registers) that selects it (empty = the gap), and — for a
    taken move — the module + resulting memory the rule lands in. The `SuccessorExpander` is the
    same engine native solution search uses, built once with the program's modules so Call rules can
    resolve their callee."""
    generator = task_context.search_context.successor_generator
    is_goal = goal_test(task_context)
    expander = GroundSuccessorExpander(task_context, program)

    def expand(graph: ProofGraph, vertices: list[int]) -> list[Successor]:
        if not isinstance(graph, GroundModuleProgramProofGraph):
            return []
        successors: list[Successor] = []
        for vertex in vertices:
            label = graph.get_vertex_property(int(vertex))
            execution_state = label.execution_state
            source_state = execution_state.state
            for labeled in generator.get_labeled_successor_nodes(Node(source_state, 0.0)):
                target_state = labeled.node.get_state()
                rule_variant = expander.matching_rule(
                    execution_state, labeled.label, target_state
                )
                rule: str | None = None
                res_module: str | None = None
                res_memory: str | None = None
                if rule_variant is not None:
                    rule = str(rule_variant.get_symbol()).strip()
                    applied = expander.apply(
                        execution_state, rule_variant, labeled.label, target_state
                    )
                    if applied is not None:
                        target_stack = applied.target.call_stack
                        res_module = target_stack.module.get_name()
                        res_memory = target_stack.memory_state.get_name()
                source_stack = execution_state.call_stack
                successors.append(
                    successor(
                        source_state,
                        target_state,
                        labeled.label,
                        rule,
                        evidence,
                        is_goal,
                        module=res_module,
                        memory=res_memory,
                        source_memory=(
                            source_stack.module.get_name(),
                            source_stack.memory_state.get_name(),
                        ),
                    )
                )
        return successors

    return expand
