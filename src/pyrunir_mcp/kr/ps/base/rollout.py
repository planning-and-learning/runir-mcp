"""Greedy single-trace policy rollout for base `execute` failures.

`find_ground_solution` (greedy SIW) is correct about *whether* a policy reaches the goal, but on a
downstream failure tyr's serialized search discards the committed rollout prefix and runir's
`proof_result_from_siw_solution` reports the **initial** vertex as the lone open state — so the
result graph has a single vertex and runir-mcp renders a useless one-state trace at `init`. (The ext
executor has its own rollout and already reports the real stuck state; only base is affected.)

This module reconstructs a real trajectory in Python: from the initial state it follows the policy
one feature-changing, rule-compatible step at a time (deterministic, measure-aware tie-break) until a
dead-end, cycle, goal, or a classifier-detected unsolvable state. It then builds the
trace/counterexample/successors documents directly via the `output.policy` builders. `execute`'s
pass/fail verdict still comes from `find_ground_solution`; this only enriches the failure witness.

An unsolvability classifier is threaded through (default: the empty `(or)` classifier, which marks no
state unsolvable) so real classifiers can flag dead states in the future with no further plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pyrunir.datasets import GroundTaskSearchContext
from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory
from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext as UnsEvaluationContext
from pyrunir.kr.ps.base import Sketch as Policy
from pyrunir.kr.ps.base.dl import GroundEvaluationContext as RuleEvaluationContext
from pyrunir.kr.uns import classify
from pytyr.formalism.planning import GroundAction
from pytyr.planning.ground import Node, State

from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.kr.ps.feature_evidence import Feature, FeatureEvidence, evaluate_features, feature_key
from pyrunir_mcp.kr.ps.frontier import _format_ground_action, _goal_test, _successor
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import Cycle, Successor, counterexample_document, successors_document, trace_document
from pyrunir_mcp.output.proof_witness import witness_state, witness_transition
from pyrunir_mcp.tables import Document

_MAX_ROLLOUT_STEPS = 1_000_000  # safety cap; the walk dedups states so it always terminates first

Outcome = Literal["deadend", "cycle", "goal", "unsolvable"]
Classifier = object  # pyrunir ClassifierView (no public type alias to import)


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
    outcome: Outcome
    cycle_start_index: int | None = None


def _decreases_numeric(before: JsonObject, after: JsonObject) -> bool:
    """True if some numerical feature strictly decreased (booleans excluded — `bool` is an `int`)."""
    for key, prior in before.items():
        nxt = after.get(key)
        if (
            isinstance(prior, (int, float))
            and not isinstance(prior, bool)
            and isinstance(nxt, (int, float))
            and not isinstance(nxt, bool)
            and nxt < prior
        ):
            return True
    return False


def _make_compatible_rule(policy: Policy, builder: Builder, denotations: object):
    rules = list(policy.get_rules())

    def compatible_rule(source: State, target: State) -> str | None:
        context = RuleEvaluationContext(source, target, builder, denotations)
        for rule in rules:
            if rule.is_compatible_with(context):
                return str(rule.get_symbol()).strip()
        return None

    return compatible_rule


def greedy_policy_rollout(
    search_context: GroundTaskSearchContext,
    policy: Policy,
    features: list[Feature],
    classifier: Classifier,
    *,
    max_steps: int = _MAX_ROLLOUT_STEPS,
) -> RolloutResult:
    fkeys = [feature_key(feature) for feature in features]
    generator = search_context.successor_generator
    is_goal = _goal_test(search_context)
    compatible_rule = _make_compatible_rule(policy, Builder(), DenotationRepositoryFactory().create())
    # A denotation repository caches per DL family; the uns classifier MUST NOT share the base-ps
    # rule-eval repository, or mixing base/uns denotations in one cache crashes runir. Dedicated here.
    uns_builder = Builder()
    uns_denotations = DenotationRepositoryFactory().create()

    def values(state: State) -> dict[str, JsonValue]:
        return evaluate_features(state, features)

    def is_unsolvable(state: State) -> bool:
        return bool(classify(classifier, UnsEvaluationContext(state, uns_builder, uns_denotations)))

    current = search_context.state_repository.get_initial_state()
    states: list[State] = [current]
    steps: list[RolloutStep] = []
    seen: dict[int, int] = {int(current.get_index()): 0}

    for _ in range(max_steps):
        if is_goal(current):
            return RolloutResult(states, steps, "goal")
        if is_unsolvable(current):
            return RolloutResult(states, steps, "unsolvable")
        current_values = values(current)
        current_fvec = tuple(current_values[key] for key in fkeys)
        # candidate := (0 if it decreases a numerical measure else 1, enumeration order, label, target, rule)
        candidates: list[tuple[int, int, GroundAction, State, str]] = []
        for order, labeled in enumerate(generator.get_labeled_successor_nodes(Node(current, 0.0))):
            target = labeled.node.get_state()
            target_values = values(target)
            if tuple(target_values[key] for key in fkeys) == current_fvec:
                continue  # only feature-changing successors are policy steps
            rule = compatible_rule(current, target)
            if rule is None:
                continue
            progress = 0 if _decreases_numeric(current_values, target_values) else 1
            candidates.append((progress, order, labeled.label, target, rule))
        if not candidates:
            return RolloutResult(states, steps, "deadend")
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
        _, _, action, target, rule = candidates[0]
        steps.append(RolloutStep(current, action, rule, target))
        states.append(target)
        target_index = int(target.get_index())
        if target_index in seen:
            return RolloutResult(states, steps, "cycle", cycle_start_index=seen[target_index])
        seen[target_index] = len(states) - 1
        current = target

    return RolloutResult(states, steps, "deadend")


def rollout_artifacts(
    search_context: GroundTaskSearchContext,
    policy: Policy,
    features: list[Feature],
    classifier: Classifier,
    evidence: FeatureEvidence,
    *,
    feature_symbols: list[str],
    dicts: Dictionaries,
    header: list[tuple[str, str]],
    max_steps: int = _MAX_ROLLOUT_STEPS,
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> tuple[Document, Document | None, Document | None, str | None] | None:
    """Build (counterexample, trace, successors) for a base init-only `execute` failure by rolling the
    policy forward to its real stuck state. Returns `None` if the greedy rollout instead reaches a goal
    (verdict and rollout disagree on tie-breaks) so the caller falls back to the default init witness.
    The fourth return value is an optional failure-category override."""
    result = greedy_policy_rollout(search_context, policy, features, classifier, max_steps=max_steps)
    if result.outcome == "goal":
        return None

    is_goal = _goal_test(search_context)
    generator = search_context.successor_generator
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    compatible_rule = _make_compatible_rule(policy, builder, denotations)
    terminal_unsolvable = result.outcome == "unsolvable"
    is_cycle = result.outcome == "cycle"
    last = len(result.states) - 1

    def summary(state: State, *, initial: bool, unsolvable: bool) -> JsonObject:
        return {
            "state_index": int(state.get_index()),
            "is_initial": initial,
            "is_goal": is_goal(state),
            "is_unsolvable": unsolvable,
            **evidence(state),
        }

    summaries = [
        summary(state, initial=(index == 0), unsolvable=(terminal_unsolvable and index == last))
        for index, state in enumerate(result.states)
    ]
    trace_states = [
        witness_state(s, witness=(index == last), open_state=(index == last and not terminal_unsolvable), cycle=(is_cycle and index == last))
        for index, s in enumerate(summaries)
    ]
    trace_transitions = [
        witness_transition(
            {"action": _format_ground_action(step.action), "module_rule": step.rule},
            step=index,
            source=summaries[index],
            target=summaries[index + 1],
            ext=False,
        )
        for index, step in enumerate(result.steps)
    ]
    trace = trace_document(
        header=header, feature_symbols=feature_symbols, states=trace_states, transitions=trace_transitions, dicts=dicts, ext=False,
        include_hstar=include_hstar, include_hlmcut=include_hlmcut,
    )

    if is_cycle:
        start = result.cycle_start_index or 0
        cycle = Cycle(
            state_indices=tuple(int(state.get_index()) for state in result.states[start:]),
            transition_steps=tuple(range(start, len(result.steps))),
        )
        counterexample = counterexample_document(
            header=header, feature_symbols=feature_symbols, states=trace_states, transitions=trace_transitions, cycle=cycle, dicts=dicts, ext=False,
            include_hstar=include_hstar, include_hlmcut=include_hlmcut,
        )
    else:
        counterexample = counterexample_document(
            header=header, feature_symbols=feature_symbols, states=[trace_states[last]], transitions=[], cycle=None, dicts=dicts, ext=False,
            include_hstar=include_hstar, include_hlmcut=include_hlmcut,
        )

    terminal = result.states[last]
    successors: list[Successor] = []
    if not terminal_unsolvable:
        successors = [
            _successor(terminal, labeled.node.get_state(), labeled.label, compatible_rule(terminal, labeled.node.get_state()), evidence, is_goal)
            for labeled in generator.get_labeled_successor_nodes(Node(terminal, 0.0))
        ]
    successors_doc = (
        successors_document(
            header=header, feature_symbols=feature_symbols, successors=successors, dicts=dicts, ext=False,
            include_hstar=include_hstar, include_hlmcut=include_hlmcut,
        )
        if successors
        else None
    )
    category_override = "deadend" if terminal_unsolvable else None
    return counterexample, trace, successors_doc, category_override
