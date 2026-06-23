"""Successor-frontier expansion for base sketch witnesses.

The proof/execution graph holds only sketch-compatible transitions, so a stuck (open) state
has no out-edges there and the graph cannot surface the moves a policy *failed* to take. To
expose the full 1-step frontier — every applicable move and which rule (if any) selects it —
we expand each state on the trace with the pytyr successor generator and mark compatibility
with pyrunir's `Sketch.is_compatible_with`. A successor that advances toward the goal with an
empty `rule` is the gap.

Base only: `pyrunir.kr.ps.ext` exposes no compatibility primitive, so the module-program
witnesses pass no expander (see `proof.witness_artifacts`).
"""

from __future__ import annotations

from collections.abc import Callable

from pyrunir.datasets import GroundTaskSearchContext
from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory
from pyrunir.kr.ps.base import Sketch
from pyrunir.kr.ps.base.dl import GroundEvaluationContext
from pytyr.formalism.planning import GroundAction
from pytyr.planning.ground import ConjunctiveGoalStrategy, Node, State

from pyrunir_mcp.kr.ps.feature_evidence import FeatureEvidence
from pyrunir_mcp.output.policy import Successor
from pyrunir_mcp.output.proof_witness import successor as build_successor

# Expand every state on a trace/cycle into its 1-step successor frontier.
FrontierExpander = Callable[[list[State]], list[Successor]]


def _format_ground_action(action: GroundAction) -> str:
    inner = action.get_action()
    arguments = ", ".join(str(obj) for obj in action.get_objects())
    return f"{inner.get_name()}({arguments})"


def make_frontier_expander(
    search_context: GroundTaskSearchContext,
    sketch: Sketch,
    evidence: FeatureEvidence,
) -> FrontierExpander:
    """Build an expander that, given the states along a trace/cycle, returns every 1-step
    successor of each — tagged with the sketch rule that selects it (or empty = the gap)."""
    generator = search_context.successor_generator
    rules = list(sketch.get_rules())
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    goal = ConjunctiveGoalStrategy(search_context.task)
    seed_state = search_context.state_repository.get_initial_state()

    def compatible_rule(source_state: State, target_state: State) -> str | None:
        context = GroundEvaluationContext(source_state, target_state, builder, denotations)
        for rule in rules:
            if rule.is_compatible_with(context):
                return str(rule.get_symbol()).strip()
        return None

    def is_goal(state: State) -> bool:
        try:
            return bool(goal.is_dynamic_goal_satisfied(seed_state, state))
        except RuntimeError:
            return False

    def expand(states: list[State]) -> list[Successor]:
        successors: list[Successor] = []
        for source_state in states:
            source = {"state_index": int(source_state.get_index()), **evidence(source_state)}
            for labeled in generator.get_labeled_successor_nodes(Node(source_state, 0.0)):
                target_state = labeled.node.get_state()
                target = {
                    "state_index": int(target_state.get_index()),
                    "is_goal": is_goal(target_state),
                    **evidence(target_state),
                }
                edge = {"action": _format_ground_action(labeled.label), "module_rule": compatible_rule(source_state, target_state)}
                successors.append(build_successor(source, edge, target))
        return successors

    return expand
