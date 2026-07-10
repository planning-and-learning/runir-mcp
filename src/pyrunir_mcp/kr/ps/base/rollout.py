"""Greedy single-trace policy rollout for base `execute` failures.

Base execute follows a single greedy policy trajectory in Python: from the initial state it follows
one policy-compatible step at a time until an open state, cycle, goal, or a classifier-detected unsolvable state. The same trajectory is used for the
execute verdict and the written trace/counterexample/successor artifacts.

An unsolvability classifier is threaded through (default: the empty `(or)` classifier, which marks no
state unsolvable) so real classifiers can flag dead states in the future with no further plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from pyrunir.datasets import GroundTaskSearchContext
from pyrunir.kr.ps.base import ExecutionContext, SuccessorExpander
from pyrunir.kr.ps.base import Sketch as Policy
from pyrunir.kr.uns import Classifier
from pytyr.formalism.planning import GroundAction
from pytyr.planning.ground import Node, State

from pyrunir_mcp.enums import RolloutOutcome
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.keys import (
    Keys,
)
from pyrunir_mcp.kr.ps.classifier import unsolvability_test
from pyrunir_mcp.kr.ps.feature_evidence import Feature, FeatureEvidence
from pyrunir_mcp.kr.ps.frontier import format_ground_action, goal_test, successor
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import (
    Successor,
    counterexample_document,
    successors_document,
    trace_document,
)
from pyrunir_mcp.output.proof_witness import witness_state, witness_transition
from pyrunir_mcp.tables import Document

_MAX_ROLLOUT_STEPS = 1_000_000  # safety cap; the walk dedups states so it always terminates first


@dataclass(frozen=True)
class RolloutStep:
    source: State
    action: GroundAction
    rule: str | None
    target: State


@dataclass(frozen=True)
class RolloutResult:
    states: list[State]
    steps: list[RolloutStep]
    outcome: RolloutOutcome
    cycle_start_index: int | None = None


def compatible_rule(
    expander: SuccessorExpander,
    context: ExecutionContext,
    target: State,
) -> str | None:
    rule = expander.matching_rule(context, target)
    return None if rule is None else str(rule.get_symbol()).strip()


def greedy_policy_rollout(
    search_context: GroundTaskSearchContext,
    policy: Policy,
    classifier: Classifier,
    *,
    max_steps: int = _MAX_ROLLOUT_STEPS,
    random_seed: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
) -> RolloutResult:
    generator = search_context.successor_generator
    is_goal = goal_test(search_context)
    is_unsolvable = unsolvability_test(classifier)
    expander = SuccessorExpander(policy)

    rng = Random(random_seed)
    current = search_context.state_repository.get_initial_state()
    current_context = expander.context_at(current)
    states: list[State] = [current]
    steps: list[RolloutStep] = []
    seen: dict[int, int] = {int(current.get_index()): 0}

    for _ in range(max_steps):
        if is_goal(current):
            return RolloutResult(states, steps, RolloutOutcome.GOAL)
        if is_unsolvable(current):
            return RolloutResult(states, steps, RolloutOutcome.UNSOLVABLE)
        selected: tuple[GroundAction, State, str] | None = None
        successors = list(generator.get_labeled_successor_nodes(Node(current, 0.0)))
        if shuffle_labeled_succ_nodes:
            rng.shuffle(successors)
        for labeled in successors:
            target = labeled.node.get_state()
            rule = compatible_rule(expander, current_context, target)
            if rule is not None:
                selected = (labeled.label, target, rule)
                break
        if selected is None:
            return RolloutResult(states, steps, RolloutOutcome.OPEN_STATE)
        action, target, rule = selected
        steps.append(RolloutStep(current, action, rule, target))
        states.append(target)
        target_index = int(target.get_index())
        if target_index in seen:
            return RolloutResult(
                states,
                steps,
                RolloutOutcome.CYCLE,
                cycle_start_index=seen[target_index],
            )
        seen[target_index] = len(states) - 1
        current = target
        current_context = expander.context_at(current)

    return RolloutResult(states, steps, RolloutOutcome.OPEN_STATE)


def rollout_category(result: RolloutResult) -> str | None:
    if result.outcome is RolloutOutcome.GOAL:
        return None
    if result.outcome is RolloutOutcome.CYCLE:
        return "cycle"
    return "deadend" if result.outcome is RolloutOutcome.UNSOLVABLE else "open_state"


def rollout_witness(result: RolloutResult) -> tuple[str, ...]:
    if result.outcome is RolloutOutcome.GOAL:
        return ()
    if result.outcome is RolloutOutcome.CYCLE:
        start = result.cycle_start_index or 0
        return tuple(f"s{int(state.get_index())}" for state in result.states[start:])
    return (f"s{int(result.states[-1].get_index())}",)


def rollout_trace_document(
    search_context: GroundTaskSearchContext,
    result: RolloutResult,
    features: list[Feature],
    evidence: FeatureEvidence,
    *,
    feature_symbols: list[str],
    dicts: Dictionaries,
    header: list[tuple[str, str]],
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> Document:
    is_goal = goal_test(search_context)
    summaries = [
        {
            Keys.STATE_INDEX: int(state.get_index()),
            Keys.IS_INITIAL: index == 0,
            Keys.IS_GOAL: is_goal(state),
            Keys.IS_UNSOLVABLE: result.outcome is RolloutOutcome.UNSOLVABLE
            and index == len(result.states) - 1,
            **evidence(state),
        }
        for index, state in enumerate(result.states)
    ]
    trace_states = [
        witness_state(
            summary,
            witness=(index == len(summaries) - 1 and result.outcome is not RolloutOutcome.GOAL),
            open_state=(
                index == len(summaries) - 1
                and result.outcome in (RolloutOutcome.OPEN_STATE, RolloutOutcome.CYCLE)
            ),
            cycle=(index == len(summaries) - 1 and result.outcome is RolloutOutcome.CYCLE),
        )
        for index, summary in enumerate(summaries)
    ]
    trace_transitions = [
        witness_transition(
            {Keys.ACTION: format_ground_action(step.action), Keys.RULE: step.rule},
            step=index,
            source=summaries[index],
            target=summaries[index + 1],
            ext=False,
        )
        for index, step in enumerate(result.steps)
    ]
    return trace_document(
        header=header,
        feature_symbols=feature_symbols,
        states=trace_states,
        transitions=trace_transitions,
        dicts=dicts,
        ext=False,
        include_hstar=include_hstar,
        include_hlmcut=include_hlmcut,
    )


def rollout_artifacts(
    search_context: GroundTaskSearchContext,
    policy: Policy,
    features: list[Feature],
    classifier: Classifier | None,
    evidence: FeatureEvidence,
    *,
    feature_symbols: list[str],
    dicts: Dictionaries,
    header: list[tuple[str, str]],
    max_steps: int = _MAX_ROLLOUT_STEPS,
    random_seed: int = 0,
    shuffle_labeled_succ_nodes: bool = True,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
    result: RolloutResult | None = None,
) -> tuple[Document, Document | None, Document | None, str | None] | None:
    """Build (counterexample, trace, successors) for a base init-only `execute` failure by rolling the
    policy forward to its real stuck state. Returns `None` if the greedy rollout instead reaches a goal
    (verdict and rollout disagree on tie-breaks) so the caller falls back to the default init witness.
    The fourth return value is an optional failure-category override."""
    if result is None:
        if classifier is None:
            raise ValueError("classifier is required when rollout result is not supplied")
        result = greedy_policy_rollout(
            search_context,
            policy,
            classifier,
            max_steps=max_steps,
            random_seed=random_seed,
            shuffle_labeled_succ_nodes=shuffle_labeled_succ_nodes,
        )
    if result.outcome is RolloutOutcome.GOAL:
        return None

    is_goal = goal_test(search_context)
    generator = search_context.successor_generator
    expander = SuccessorExpander(policy)
    terminal_unsolvable = result.outcome is RolloutOutcome.UNSOLVABLE
    is_cycle = result.outcome is RolloutOutcome.CYCLE
    last = len(result.states) - 1

    def summary(state: State, *, initial: bool, unsolvable: bool) -> JsonObject:
        return {
            Keys.STATE_INDEX: int(state.get_index()),
            Keys.IS_INITIAL: initial,
            Keys.IS_GOAL: is_goal(state),
            Keys.IS_UNSOLVABLE: unsolvable,
            **evidence(state),
        }

    summaries = [
        summary(state, initial=(index == 0), unsolvable=(terminal_unsolvable and index == last))
        for index, state in enumerate(result.states)
    ]
    trace_states = [
        witness_state(
            s,
            witness=(index == last),
            open_state=(index == last and not terminal_unsolvable),
            cycle=(is_cycle and index == last),
        )
        for index, s in enumerate(summaries)
    ]
    trace_transitions = [
        witness_transition(
            {Keys.ACTION: format_ground_action(step.action), Keys.RULE: step.rule},
            step=index,
            source=summaries[index],
            target=summaries[index + 1],
            ext=False,
        )
        for index, step in enumerate(result.steps)
    ]
    trace = trace_document(
        header=header,
        feature_symbols=feature_symbols,
        states=trace_states,
        transitions=trace_transitions,
        dicts=dicts,
        ext=False,
        include_hstar=include_hstar,
        include_hlmcut=include_hlmcut,
    )

    if is_cycle:
        start = result.cycle_start_index or 0
        cycle_states = trace_states[start:]
        cycle_transitions = trace_transitions[start:]
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=cycle_states,
            transitions=cycle_transitions,
            cycle=True,
            dicts=dicts,
            ext=False,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
    else:
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=[trace_states[last]],
            transitions=[],
            cycle=False,
            dicts=dicts,
            ext=False,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )

    terminal = result.states[last]
    terminal_context = expander.context_at(terminal)
    successors: list[Successor] = []
    if not terminal_unsolvable:
        successors = [
            successor(
                terminal,
                labeled.node.get_state(),
                labeled.label,
                compatible_rule(expander, terminal_context, labeled.node.get_state()),
                evidence,
                is_goal,
            )
            for labeled in generator.get_labeled_successor_nodes(Node(terminal, 0.0))
        ]
    successors_doc = (
        successors_document(
            header=header,
            feature_symbols=feature_symbols,
            successors=successors,
            dicts=dicts,
            ext=False,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        if successors
        else None
    )
    category_override = "deadend" if terminal_unsolvable else "cycle" if is_cycle else None
    return counterexample, trace, successors_doc, category_override
