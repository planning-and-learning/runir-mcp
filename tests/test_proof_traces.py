from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pyrunir_mcp.proof import counterexample_data, edge_summary


class Label:
    def __init__(self, state_id: int, *, initial: bool = False):
        self.state = SimpleNamespace(get_index=lambda: state_id)
        self.is_initial = initial


class Graph:
    def __init__(self):
        self.vertices = {0: Label(10, initial=True), 1: Label(11), 2: Label(12)}
        self.edges = {0: (0, 1), 1: (1, 2)}

    def get_vertex_indices(self):
        return list(self.vertices)

    def get_out_edge_indices(self, vertex):
        return [edge for edge, (source, _target) in self.edges.items() if source == vertex]

    def get_vertex_property(self, vertex):
        return self.vertices[vertex]

    def get_num_vertices(self):
        return len(self.vertices)

    def get_num_edges(self):
        return len(self.edges)

    def get_source(self, edge):
        return self.edges[edge][0]

    def get_target(self, edge):
        return self.edges[edge][1]

    def get_edge_property(self, edge):
        action_schema = SimpleNamespace(get_name=lambda: "move", get_original_arity=lambda: 2)
        class Row:
            def __str__(self):
                return f"(room{edge}a room{edge}b)"

        action = SimpleNamespace(get_action=lambda: action_schema, get_row=Row)
        return SimpleNamespace(
            rule=SimpleNamespace(get_symbol=lambda: f"rule-{edge}"),
            transition=SimpleNamespace(action=action),
        )


def test_open_state_counterexample_includes_initial_to_witness_trace():
    task = SimpleNamespace(problem_path=Path("p1.pddl"))
    result = SimpleNamespace(graph=Graph(), status=SimpleNamespace(name="FAILURE"))

    data = counterexample_data(task, result, "open_state", 2)

    assert data["trace"]["trace_available"] is True
    assert data["trace"]["path_edges"] == [0, 1]
    assert [state["state_id"] for state in data["trace"]["states"]] == [10, 11, 12]
    assert [(edge["source"], edge["target"]) for edge in data["trace"]["transitions"]] == [(0, 1), (1, 2)]
    assert [edge["action"] for edge in data["trace"]["transitions"]] == [
        "move(room0a, room0b)",
        "move(room1a, room1b)",
    ]
    assert [edge["module_rule"] for edge in data["trace"]["transitions"]] == [
        "rule-0",
        "rule-1",
    ]
    assert data["states"] == data["trace"]["states"]


def test_module_program_edge_summary_uses_state_transition_action_and_rule_symbol():
    action_schema = SimpleNamespace(get_name=lambda: "move", get_original_arity=lambda: 2)
    class Row:
        def __str__(self):
            return "(rooma roomb)"

    state_transition = SimpleNamespace(
        action=SimpleNamespace(get_action=lambda: action_schema, get_row=Row)
    )
    rule = SimpleNamespace(get_symbol=lambda: "do-move")
    graph = SimpleNamespace(
        get_source=lambda edge: 1,
        get_target=lambda edge: 2,
        get_edge_property=lambda edge: SimpleNamespace(state_transition=state_transition, rule=rule),
    )

    assert edge_summary(graph, 7) == {
        "edge": 7,
        "source": 1,
        "target": 2,
        "action": "move(rooma, roomb)",
        "module_rule": "do-move",
        "transition": str(state_transition),
    }


def test_module_program_load_edge_summary_uses_rule_symbol_without_action():
    rule = SimpleNamespace(get_symbol=lambda: "load")
    graph = SimpleNamespace(
        get_source=lambda edge: 1,
        get_target=lambda edge: 2,
        get_edge_property=lambda edge: SimpleNamespace(state_transition=None, rule=rule),
    )

    assert edge_summary(graph, 8) == {
        "edge": 8,
        "source": 1,
        "target": 2,
        "module_rule": "load",
    }
