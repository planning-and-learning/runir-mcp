"""Successor-frontier expansion for policy witnesses (base sketch + ext module program).

The proof/execution graph holds only policy-compatible transitions, so a stuck (open) state
has no out-edges there and the graph cannot surface the moves a policy *failed* to take. To
expose the full 1-step frontier — every applicable move and which rule (if any) selects it —
we expand each state on the trace with the pytyr successor generator and mark compatibility
with the policy:

- base: `Sketch.is_compatible_with(GroundEvaluationContext(source, target))`;
- ext:  `pyrunir.kr.ps.ext.SuccessorExpander`, whose `matching_rule(...)` replays the
  module-program executor's per-rule applicability (memory match + conditions + effects, DoRule
  action match) at the vertex's memory state + registers, and whose `apply(...)` returns the
  resulting proof node so each taken move can report the module + memory it lands in.

A successor that advances toward the goal with an empty `rule` is the gap. Successors are
off-graph planning moves (no proof vertex), so they are emitted state-indexed; ext additionally
carries source and target module/memory context per taken move (see `proof.witness_artifacts`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeAlias, cast

from pyrunir.datasets import GroundTaskSearchContext
from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory
from pyrunir.kr.ps.base import GroundSketchProofGraph, Sketch
from pyrunir.kr.ps.base.dl import GroundEvaluationContext
from pyrunir.kr.ps.ext import (
    ExternalMemoryState,
    GroundModuleProgramProofGraph,
    InternalMemoryState,
    MemoryState,
    ModuleProgram,
    SuccessorExpander,
)
from pytyr.formalism.planning import GroundAction
from pytyr.planning.ground import ConjunctiveGoalStrategy, Node, State

from pyrunir_mcp.kr.ps.feature_evidence import FeatureEvidence
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.output.policy import Successor
from pyrunir_mcp.output.proof_witness import successor as build_successor

# Expand the deduped trace/cycle vertices of a proof graph into their 1-step successor frontier.
ProofGraph: TypeAlias = GroundSketchProofGraph | GroundModuleProgramProofGraph
FrontierExpander: TypeAlias = Callable[[ProofGraph, list[int]], list[Successor]]


def format_ground_action(action: GroundAction) -> str:
    inner = action.get_action()
    arguments = ", ".join(str(obj) for obj in action.get_objects())
    return f"{inner.get_name()}({arguments})"


def goal_test(search_context: GroundTaskSearchContext) -> Callable[[State], bool]:
    goal = ConjunctiveGoalStrategy(search_context.task)
    seed_state = search_context.state_repository.get_initial_state()

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
    source = {"state_index": int(source_state.get_index()), **evidence(source_state)}
    if source_memory is not None:
        source["module"], source["memory_state"] = source_memory
    target = {"state_index": int(target_state.get_index()), "is_goal": is_goal(target_state), **evidence(target_state)}
    if module is not None:
        target["module"] = module
        target["memory_state"] = memory
    edge: JsonObject = {"action": format_ground_action(action), "module_rule": rule}
    return build_successor(source, edge, target)


def make_frontier_expander(
    search_context: GroundTaskSearchContext,
    sketch: Sketch,
    evidence: FeatureEvidence,
) -> FrontierExpander:
    """Base sketch: every 1-step successor of each trace vertex's state, tagged with the sketch
    rule that selects it (empty = the gap)."""
    generator = search_context.successor_generator
    rules = list(sketch.get_rules())
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    is_goal = goal_test(search_context)

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


class _NamedMemory(Protocol):
    def get_name(self) -> object: ...


def _memory_name(memory_state: MemoryState) -> str:
    # Pybind memory-state stubs do not expose get_name(), but the runtime object does.
    return str(cast(_NamedMemory, memory_state).get_name())


def _wrapped_memory_name(memory_state: InternalMemoryState | ExternalMemoryState) -> str:
    # Internal/external wrappers expose the runtime memory object through value.
    return str(cast(_NamedMemory, memory_state.value).get_name())


def make_ext_frontier_expander(
    search_context: GroundTaskSearchContext,
    program: ModuleProgram,
    evidence: FeatureEvidence,
) -> FrontierExpander:
    """Module program: every 1-step successor of each trace vertex's state, tagged with the module
    rule (at the vertex's memory state + registers) that selects it (empty = the gap), and — for a
    taken move — the module + resulting memory the rule lands in. The `SuccessorExpander` is the
    same engine the executor/prover uses, built once with the program's modules so Call rules can
    resolve their callee."""
    generator = search_context.successor_generator
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    is_goal = goal_test(search_context)
    initial_state = search_context.state_repository.get_initial_state()
    expander = SuccessorExpander(search_context, initial_state, list(program.get_modules()), builder, denotations)

    def expand(graph: ProofGraph, vertices: list[int]) -> list[Successor]:
        if not isinstance(graph, GroundModuleProgramProofGraph):
            return []
        successors: list[Successor] = []
        for vertex in vertices:
            label = graph.get_vertex_property(int(vertex))
            source_state = label.state
            memory = label.memory_state
            memory = memory.value if hasattr(memory, "value") else memory
            # pyrunir sometimes exposes memory as a pybind value wrapper; normalize to the wrapped type.
            memory = cast(MemoryState, memory)
            concept_registers = label.concept_registers
            role_registers = label.role_registers
            module = label.module
            for labeled in generator.get_labeled_successor_nodes(Node(source_state, 0.0)):
                target_state = labeled.node.get_state()
                rule_variant = expander.matching_rule(
                    module, memory, concept_registers, role_registers, source_state, labeled.label, target_state
                )
                rule: str | None = None
                res_module: str | None = None
                res_memory: str | None = None
                if rule_variant is not None:
                    rule = str(rule_variant.get_symbol()).strip()
                    applied = expander.apply(
                        module, memory, concept_registers, role_registers, source_state, rule_variant, labeled.label, target_state
                    )
                    if applied is not None:
                        _edge, node = applied
                        res_module = str(node.module.get_name())
                        res_memory = _wrapped_memory_name(node.memory_state)
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
                        source_memory=(str(module.get_name()), _memory_name(memory)),
                    )
                )
        return successors

    return expand

