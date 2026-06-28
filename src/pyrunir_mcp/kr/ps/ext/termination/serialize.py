from __future__ import annotations

from pyrunir.kr.ps.ext import StructuralTerminationStatus

from pyrunir_mcp.json_types import JsonObject


def feature_symbol(feature) -> str:
    return str(feature.get_variant().get_symbol()).strip()


def rule_symbol(rule) -> str:
    return str(rule.get_symbol()).strip()


def string_keyed_dict(values) -> dict[str, str]:
    return {feature_symbol(key): str(value) for key, value in values.items()}


def counterexample_to_data(counterexample) -> JsonObject:
    vertices = []
    for index, vertex in enumerate(counterexample.get_vertices()):
        vertices.append(
            {
                "index": index,
                "memory_state": str(vertex.get_memory_state()),
                "concepts": string_keyed_dict(vertex.get_concepts()),
                "booleans": string_keyed_dict(vertex.get_booleans()),
                "numericals": string_keyed_dict(vertex.get_numericals()),
            }
        )

    edges = []
    for index, edge in enumerate(counterexample.get_edges()):
        edges.append(
            {
                "index": index,
                "source": edge.get_source(),
                "target": edge.get_target(),
                "rule": rule_symbol(edge.get_rule()),
                "numerical_changes": string_keyed_dict(edge.get_numerical_changes()),
            }
        )

    return {
        "num_vertices": counterexample.get_num_vertices(),
        "num_edges": counterexample.get_num_edges(),
        "vertices": vertices,
        "edges": edges,
    }


def status_name(status: StructuralTerminationStatus) -> str:
    return status.name
