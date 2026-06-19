from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pyrunir_mcp.proof import counterexample_data


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
        return SimpleNamespace(rule=f"rule-{edge}")


def test_open_state_counterexample_includes_initial_to_witness_trace():
    task = SimpleNamespace(problem_path=Path("p1.pddl"))
    result = SimpleNamespace(graph=Graph(), status=SimpleNamespace(name="FAILURE"))

    data = counterexample_data(task, result, "open_state", 2)

    assert data["trace"]["trace_available"] is True
    assert data["trace"]["path_edges"] == [0, 1]
    assert [state["state_id"] for state in data["trace"]["states"]] == [10, 11, 12]
    assert [(edge["source"], edge["target"]) for edge in data["trace"]["transitions"]] == [(0, 1), (1, 2)]
    assert data["states"] == data["trace"]["states"]
