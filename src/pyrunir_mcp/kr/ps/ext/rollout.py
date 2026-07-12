"""Greedy single-trace module-program rollout for ext `execute` failures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from pyrunir.kr import GroundTaskContext
from pyrunir.kr.ps.ext import (
    GroundModuleProgramSearchOptions,
    ModuleProgram,
    ModuleProgramExecutionContext,
    ModuleProgramExecutionStep,
    SuccessorExpander,
)
from pyrunir.kr.uns import Classifier
from pytyr.planning.ground import Node, State

from pyrunir_mcp.enums import RolloutOutcome
from pyrunir_mcp.json_types import JsonObject
from pyrunir_mcp.keys import (
    Keys,
)
from pyrunir_mcp.kr.ps.classifier import unsolvability_test
from pyrunir_mcp.kr.ps.feature_evidence import Feature, FeatureEvidence
from pyrunir_mcp.kr.ps.frontier import format_ground_action, goal_test
from pyrunir_mcp.kr.ps.frontier import successor as planning_successor
from pyrunir_mcp.output.dictionaries import Dictionaries
from pyrunir_mcp.output.policy import (
    Successor,
    counterexample_document,
    successors_document,
    trace_document,
)
from pyrunir_mcp.output.proof_witness import witness_state, witness_transition
from pyrunir_mcp.tables import Document

_MAX_ROLLOUT_STEPS = 1_000_000


Context: TypeAlias = ModuleProgramExecutionContext
NativeStep: TypeAlias = ModuleProgramExecutionStep


@dataclass(frozen=True)
class ExtRolloutStep:
    source: Context
    native_step: NativeStep
    target: Context


@dataclass(frozen=True)
class ExtRolloutResult:
    contexts: list[Context]
    steps: list[ExtRolloutStep]
    outcome: RolloutOutcome
    cycle_start_index: int | None = None


def _memory_name(context: Context) -> str:
    return context.call_stack.memory_state.get_name()


def _rule_symbol(step: NativeStep) -> str | None:
    edge = step.edge
    if edge is None or edge.rule is None:
        return None
    return str(edge.rule.get_symbol()).strip()


def _action_symbol(step: NativeStep) -> str | None:
    edge = step.edge
    if edge is None or edge.state_transition is None:
        return None
    return format_ground_action(edge.state_transition.action)


def _is_applied(step: NativeStep) -> bool:
    return step.status in {"applied", "restored_caller"}


def _terminal_outcome(status: str) -> RolloutOutcome:
    if status == "out_of_time":
        return RolloutOutcome.OUT_OF_TIME
    if status == "out_of_states":
        return RolloutOutcome.OUT_OF_STATES
    return RolloutOutcome.OPEN_STATE


def _make_expander(task_context: GroundTaskContext, program: ModuleProgram) -> SuccessorExpander:
    initial = task_context.search_context.state_repository.get_initial_state()
    return SuccessorExpander(
        task_context,
        initial,
        program,
    )


def greedy_module_program_rollout(
    task_context: GroundTaskContext,
    program: ModuleProgram,
    classifier: Classifier,
    options: GroundModuleProgramSearchOptions,
    *,
    max_steps: int = _MAX_ROLLOUT_STEPS,
) -> ExtRolloutResult:
    expander = _make_expander(task_context, program)
    is_goal = goal_test(task_context)
    is_unsolvable = unsolvability_test(task_context, classifier)
    current = expander.initial_context()
    contexts: list[Context] = [current]
    steps: list[ExtRolloutStep] = []
    seen: dict[Context, int] = {current: 0}

    for _ in range(max_steps):
        if is_goal(current.state):
            return ExtRolloutResult(contexts, steps, RolloutOutcome.GOAL)
        if is_unsolvable(current.state):
            return ExtRolloutResult(contexts, steps, RolloutOutcome.UNSOLVABLE)

        while True:
            load_steps = expander.load_steps(current)
            if not load_steps:
                break
            load = load_steps[0]
            if not _is_applied(load):
                return ExtRolloutResult(contexts, steps, _terminal_outcome(load.status))
            target = load.target
            steps.append(ExtRolloutStep(current, load, target))
            contexts.append(target)
            if target in seen:
                return ExtRolloutResult(contexts, steps, RolloutOutcome.CYCLE, seen[target])
            seen[target] = len(contexts) - 1
            current = target
            if is_goal(current.state):
                return ExtRolloutResult(contexts, steps, RolloutOutcome.GOAL)

        control_steps = expander.control_steps(current, options)
        control = control_steps[0]
        if not _is_applied(control):
            return ExtRolloutResult(contexts, steps, _terminal_outcome(control.status))
        target = control.target
        steps.append(ExtRolloutStep(current, control, target))
        contexts.append(target)
        if target in seen:
            return ExtRolloutResult(contexts, steps, RolloutOutcome.CYCLE, seen[target])
        seen[target] = len(contexts) - 1
        current = target

    return ExtRolloutResult(contexts, steps, RolloutOutcome.OPEN_STATE)


def ext_rollout_category(result: ExtRolloutResult) -> str | None:
    if result.outcome is RolloutOutcome.GOAL:
        return None
    if result.outcome is RolloutOutcome.CYCLE:
        return "cycle"
    return "deadend" if result.outcome is RolloutOutcome.UNSOLVABLE else "open_state"


def ext_rollout_witness(result: ExtRolloutResult) -> tuple[str, ...]:
    if result.outcome is RolloutOutcome.GOAL:
        return ()
    if result.outcome is RolloutOutcome.CYCLE:
        start = result.cycle_start_index or 0
        return tuple(_context_id(context) for context in result.contexts[start:])
    return (_context_id(result.contexts[-1]),)


def _context_id(context: Context) -> str:
    return f"{context.call_stack.module.get_name()}|{_memory_name(context)}|s{int(context.state.get_index())}"


def _summary(
    context: Context,
    evidence: FeatureEvidence,
    is_goal: Callable[[State], bool],
    *,
    initial: bool,
    unsolvable: bool = False,
) -> JsonObject:
    state = context.state
    return {
        Keys.STATE_INDEX: int(state.get_index()),
        Keys.MODULE: context.call_stack.module.get_name(),
        Keys.MEMORY: _memory_name(context),
        Keys.IS_INITIAL: initial,
        Keys.IS_GOAL: is_goal(state),
        Keys.IS_UNSOLVABLE: unsolvable,
        **evidence(state),
    }


def rollout_trace_document(
    task_context: GroundTaskContext,
    result: ExtRolloutResult,
    features: list[Feature],
    evidence: FeatureEvidence,
    *,
    feature_symbols: list[str],
    dicts: Dictionaries,
    header: list[tuple[str, str]],
    include_hstar: bool = True,
    include_hlmcut: bool = True,
) -> Document:
    is_goal = goal_test(task_context)
    last = len(result.contexts) - 1
    summaries = [
        _summary(
            context,
            evidence,
            is_goal,
            initial=index == 0,
            unsolvable=index == last and result.outcome is RolloutOutcome.UNSOLVABLE,
        )
        for index, context in enumerate(result.contexts)
    ]
    states = [
        witness_state(
            summary,
            witness=(index == last and result.outcome is not RolloutOutcome.GOAL),
            open_state=(index == last and result.outcome is RolloutOutcome.OPEN_STATE),
            cycle=(index == last and result.outcome is RolloutOutcome.CYCLE),
        )
        for index, summary in enumerate(summaries)
    ]
    transitions = [
        witness_transition(
            {Keys.ACTION: _action_symbol(step.native_step), Keys.RULE: _rule_symbol(step.native_step)},
            step=index,
            source=summaries[index],
            target=summaries[index + 1],
            ext=True,
        )
        for index, step in enumerate(result.steps)
    ]
    return trace_document(
        header=header,
        feature_symbols=feature_symbols,
        states=states,
        transitions=transitions,
        dicts=dicts,
        ext=True,
        include_hstar=include_hstar,
        include_hlmcut=include_hlmcut,
    )


def rollout_artifacts(
    task_context: GroundTaskContext,
    program: ModuleProgram,
    options: GroundModuleProgramSearchOptions,
    features: list[Feature],
    classifier: Classifier | None,
    evidence: FeatureEvidence,
    *,
    feature_symbols: list[str],
    dicts: Dictionaries,
    header: list[tuple[str, str]],
    include_hstar: bool = True,
    include_hlmcut: bool = True,
    result: ExtRolloutResult | None = None,
) -> tuple[Document, Document | None, Document | None, str | None] | None:
    if result is None:
        if classifier is None:
            raise ValueError("classifier is required when rollout result is not supplied")
        result = greedy_module_program_rollout(task_context, program, classifier, options)
    if result.outcome is RolloutOutcome.GOAL:
        return None

    is_goal = goal_test(task_context)
    last = len(result.contexts) - 1
    summaries = [
        _summary(
            context,
            evidence,
            is_goal,
            initial=index == 0,
            unsolvable=index == last and result.outcome is RolloutOutcome.UNSOLVABLE,
        )
        for index, context in enumerate(result.contexts)
    ]
    trace = rollout_trace_document(
        task_context,
        result,
        features,
        evidence,
        feature_symbols=feature_symbols,
        dicts=dicts,
        header=header,
        include_hstar=include_hstar,
        include_hlmcut=include_hlmcut,
    )
    trace_states = [
        witness_state(
            summary,
            witness=(index == last),
            open_state=(index == last and result.outcome is RolloutOutcome.OPEN_STATE),
            cycle=(index == last and result.outcome is RolloutOutcome.CYCLE),
        )
        for index, summary in enumerate(summaries)
    ]

    if result.outcome is RolloutOutcome.CYCLE:
        start = result.cycle_start_index or 0
        cycle_states = trace_states[start:]
        cycle_transitions = [
            witness_transition(
                {Keys.ACTION: _action_symbol(step.native_step), Keys.RULE: _rule_symbol(step.native_step)},
                step=index,
                source=summaries[start + index],
                target=summaries[start + index + 1],
                ext=True,
            )
            for index, step in enumerate(result.steps[start:])
        ]
        counterexample = counterexample_document(
            header=header,
            feature_symbols=feature_symbols,
            states=cycle_states,
            transitions=cycle_transitions,
            cycle=True,
            dicts=dicts,
            ext=True,
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
            ext=True,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )

    terminal = result.contexts[-1]
    expander = _make_expander(task_context, program)
    successors: list[Successor] = []
    if result.outcome is RolloutOutcome.OPEN_STATE:
        for labeled in task_context.search_context.successor_generator.get_labeled_successor_nodes(Node(terminal.state, 0.0)):
            target_state: State = labeled.node.get_state()
            rule = expander.matching_rule(terminal, labeled.label, target_state)
            edge = {
                Keys.ACTION: format_ground_action(labeled.label),
                Keys.RULE: None if rule is None else str(rule.get_symbol()).strip(),
            }
            successors.append(planning_successor(
                terminal.state,
                target_state,
                labeled.label,
                edge[Keys.RULE],
                evidence,
                is_goal,
                source_memory=(terminal.call_stack.module.get_name(), _memory_name(terminal)),
            ))
    successors_doc = (
        successors_document(
            header=header,
            feature_symbols=feature_symbols,
            successors=successors,
            dicts=dicts,
            ext=True,
            include_hstar=include_hstar,
            include_hlmcut=include_hlmcut,
        )
        if successors
        else None
    )
    return counterexample, trace, successors_doc, None
