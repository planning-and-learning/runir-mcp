from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from pyrunir_mcp.json_types import JsonObject

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.base.semantics import Builder, DenotationRepositoryFactory
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLRepositoryFactory
try:
    from pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
except ImportError:
    from pyrunir._pyrunir.kr.dl.uns.semantics import GroundEvaluationContext
from pyrunir.kr.uns import RepositoryFactory, classify
from pyrunir.kr.uns.dl import parse_classifier
from pyyggdrasil.execution import ExecutionContext
from pytyr.formalism.planning import Parser
from pytyr.planning.ground import ConjunctiveGoalStrategy, State

from pyrunir_mcp.artifacts import write_native_counterexample_run
from pyrunir_mcp.kr.uns.schemas import ProveClassifierOptions
from pyrunir_mcp.kr.uns.serialize import feature_values, fluent_facts
from pyrunir_mcp.planning import build_ground_search_context, get_problem_paths

TOOL_NAME = "runir.uns.prove_classifier"
EMPTY_CLASSIFIER = '(:classifier (:symbol c0) (:description "") (:features) (:expression (or)))'


class ResourceLimit(RuntimeError):
    pass


@dataclass
class StateSpace:
    problem_path: Path
    states: dict[int, State]
    edges: list[tuple[int, int]]
    goals: set[int]
    solvable: set[int] = field(default_factory=set)

    @property
    def unsolvable(self) -> set[int]:
        return set(self.states) - self.solvable


def _expand(domain_path: Path, problem_path: Path, max_num_states: int, ctx: ExecutionContext) -> StateSpace:
    search_context = build_ground_search_context(domain_path, problem_path, ctx)
    succ = search_context.successor_generator
    goal = ConjunctiveGoalStrategy(search_context.task)

    initial = succ.get_initial_node()
    init_state = initial.get_state()
    init_id = int(init_state.get_index())
    states: dict[int, State] = {init_id: init_state}
    edges: list[tuple[int, int]] = []
    goals: set[int] = set()
    seen = {init_id}
    queue = deque([initial])

    while queue:
        node = queue.popleft()
        state = node.get_state()
        sid = int(state.get_index())
        if goal.is_dynamic_goal_satisfied(init_state, state):
            goals.add(sid)
        for labeled in succ.get_labeled_successor_nodes(node):
            succ_state = labeled.node.get_state()
            ssid = int(succ_state.get_index())
            edges.append((sid, ssid))
            if ssid not in seen:
                seen.add(ssid)
                states[ssid] = succ_state
                if len(seen) > max_num_states:
                    raise ResourceLimit(f"{problem_path.name}: exceeded max_num_states={max_num_states}")
                queue.append(labeled.node)

    space = StateSpace(problem_path=problem_path, states=states, edges=edges, goals=goals)
    space.solvable = _backward_solvable(space)
    return space


def _backward_solvable(space: StateSpace) -> set[int]:
    reverse: dict[int, list[int]] = {state_id: [] for state_id in space.states}
    for src, dst in space.edges:
        reverse.setdefault(dst, []).append(src)
    solvable = set(space.goals)
    queue = deque(space.goals)
    while queue:
        state_id = queue.popleft()
        for predecessor in reverse.get(state_id, ()):
            if predecessor not in solvable:
                solvable.add(predecessor)
                queue.append(predecessor)
    return solvable


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = UnsDLRepositoryFactory().create(planning_domain)
    classifier_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, classifier_repository


def prove_classifier(options: ProveClassifierOptions) -> JsonObject:
    # Full enumeration is currently state-bounded; keep max_time_seconds in the
    # options schema for API consistency, but do not mutate frozen options.
    domain_path = Path(options.domain).resolve()
    train_path = Path(options.train_dir).resolve()
    planning_domain, repository = _repositories(domain_path)
    description = (
        Path(options.classifier_file).read_text(encoding="utf-8")
        if options.classifier_file is not None
        else EMPTY_CLASSIFIER
    )
    classifier = parse_classifier(description, planning_domain, repository)
    builder = Builder()
    denotations = DenotationRepositoryFactory().create()
    ctx = ExecutionContext(1)

    counterexamples: list[JsonObject] = []
    per_task: list[JsonObject] = []
    for problem_path in get_problem_paths(train_path):
        try:
            space = _expand(domain_path, problem_path, options.max_num_states, ctx)
        except ResourceLimit as exc:
            per_task.append({"task": problem_path.name, "status": "resource_limit", "reason": str(exc)})
            counterexamples.append(
                {
                    "task": problem_path.name,
                    "problem_path": problem_path.as_posix(),
                    "category": "resource_limit",
                    "reason": str(exc),
                }
            )
            continue
        task_counterexamples = 0
        for state_id, state in sorted(space.states.items()):
            eval_context = GroundEvaluationContext(state, builder, denotations)
            predicted_unsolvable = bool(classify(classifier, eval_context))
            actually_solvable = state_id in space.solvable
            if predicted_unsolvable and actually_solvable:
                category = "false_positive"
            elif not predicted_unsolvable and not actually_solvable:
                category = "false_negative"
            else:
                continue
            task_counterexamples += 1
            counterexamples.append(
                {
                    "task": problem_path.name,
                    "problem_path": problem_path.as_posix(),
                    "category": category,
                    "state_id": int(state_id),
                    "predicted_unsolvable": predicted_unsolvable,
                    "actually_solvable": actually_solvable,
                    "feature_values": feature_values(classifier, eval_context),
                    "fluent_facts": fluent_facts(state),
                }
            )
        per_task.append(
            {
                "task": problem_path.name,
                "status": "correct" if task_counterexamples == 0 else "counterexample",
                "states": len(space.states),
                "unsolvable": len(space.unsolvable),
                "counterexamples": task_counterexamples,
            }
        )

    status = "success" if not counterexamples else "failure"
    return write_native_counterexample_run(
        tool=TOOL_NAME,
        status=status,
        output_dir=Path(options.output_dir).resolve(),
        metadata={
            "domain": domain_path.as_posix(),
            "train_dir": train_path.as_posix(),
            "classifier_file": options.classifier_file,
            "max_num_states": options.max_num_states,
            "per_task": per_task,
        },
        counterexamples=counterexamples,
    )
