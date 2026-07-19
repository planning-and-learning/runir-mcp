from collections.abc import Iterator

import pytest

from pyrunir_mcp.dumping import first_directed_cycle


class DirectedGraph:
    def __init__(self, vertices: list[int], edges: list[tuple[int, int]]) -> None:
        self.vertices = vertices
        self.edges = edges

    def get_vertex_indices(self) -> Iterator[int]:
        return iter(self.vertices)

    def get_out_edge_indices(self, vertex: int) -> Iterator[int]:
        return (index for index, (source, _) in enumerate(self.edges) if source == vertex)

    def get_target(self, edge: int) -> int:
        return self.edges[edge][1]


def test_first_directed_cycle_accepts_first_self_loop() -> None:
    graph = DirectedGraph([0, 1], [(0, 0), (0, 1), (1, 0)])

    assert first_directed_cycle(graph) == ([0], [0])


def test_first_directed_cycle_excludes_path_and_unrelated_edges() -> None:
    graph = DirectedGraph([0, 1, 2, 3], [(0, 1), (0, 3), (1, 2), (2, 1), (3, 3)])

    assert first_directed_cycle(graph) == ([1, 2], [2, 3])


def test_first_directed_cycle_rejects_acyclic_graph() -> None:
    graph = DirectedGraph([0, 1, 2], [(0, 1), (1, 2)])

    with pytest.raises(ValueError, match="contains no directed cycle"):
        first_directed_cycle(graph)
