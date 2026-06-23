from __future__ import annotations

from tests.support.artifacts import assert_common_output, read_json, write_example_tool_output


def test_prove_classifier_writes_all_classifier_counterexamples_separately(tmp_path):
    result = write_example_tool_output(
        tmp_path,
        tool="runir.uns.prove_classifier",
        counterexamples=[
            {
                "task": "p-003.pddl",
                "category": "false_positive",
                "state_index": 12,
                "predicted_unsolvable": True,
                "actually_solvable": True,
                "feature_values": {"deadend_like": True},
                "fluent_facts": ["(at truck loc1)"],
            },
            {
                "task": "p-003.pddl",
                "category": "false_negative",
                "state_index": 13,
                "predicted_unsolvable": False,
                "actually_solvable": False,
                "feature_values": {"deadend_like": False},
                "fluent_facts": ["(at truck loc2)"],
            },
        ],
    )

    run_dir = tmp_path / "run"
    summary = assert_common_output(run_dir, result, expected_count=2)
    assert summary["by_category"]["false_positive"]["count"] == 1
    assert summary["by_category"]["false_negative"]["count"] == 1
    assert summary["counts"]["tasks_with_counterexamples"] == 1

    fp_item = summary["by_category"]["false_positive"]["items"][0]
    fn_item = summary["by_category"]["false_negative"]["items"][0]
    assert fp_item["trace_path"] is None
    assert fn_item["trace_path"] is None
    assert fp_item["trace_available"] is False
    assert fn_item["trace_available"] is False
    fp = read_json(run_dir / fp_item["path"])
    fn = read_json(run_dir / fn_item["path"])
    assert fp["feature_values"] == {"deadend_like": True}
    assert fn["feature_values"] == {"deadend_like": False}


def test_prove_classifier_accepts_frozen_options(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from pyrunir_mcp.kr.uns import service
    from pyrunir_mcp.kr.uns.schemas import ProveClassifierOptions

    domain = tmp_path / "domain.pddl"
    classifier = tmp_path / "classifier.txt"
    output = tmp_path / "out"
    domain.write_text("(define (domain d))\n", encoding="utf-8")
    classifier.write_text('(:classifier (:symbol c0) (:description "") (:features) (:expression (or)))\n', encoding="utf-8")

    descriptions = []

    def fake_parse(description, _domain, _repo):
        descriptions.append(description)
        return SimpleNamespace(get_features=lambda: [])

    empty_graph = SimpleNamespace(get_num_vertices=lambda: 0, get_vertex_indices=lambda: [])
    monkeypatch.setattr(service, "_repositories", lambda _domain: (object(), object()))
    monkeypatch.setattr(service, "parse_classifier", fake_parse)
    monkeypatch.setattr(service, "build_ground_search_context", lambda *_a, **_k: object())
    monkeypatch.setattr(service, "generate_ground_state_graph_result", lambda *_a, **_k: SimpleNamespace(status=service.SearchStatus.EXHAUSTED, graph=object()))
    monkeypatch.setattr(service, "annotate_ground_state_graph", lambda *_a, **_k: SimpleNamespace(get_forward_graph=lambda: empty_graph))

    result = service.prove_classifier(
        ProveClassifierOptions(
            domain_file=str(domain),
            problem_file=str(tmp_path / "p1.pddl"),
            output_dir=str(output),
            classifier_file=str(classifier),
            max_time_seconds=0.01,
        )
    )

    assert descriptions == [classifier.read_text(encoding="utf-8")]
    assert result["status"] == "success"
    assert result["primary"]["successful"] is True


def test_create_empty_classifier_writes_empty_classifier(tmp_path):
    from pyrunir_mcp.kr.uns.reformat import service
    from pyrunir_mcp.kr.uns.reformat.service import CreateEmptyClassifierOptions

    classifier = tmp_path / "classifier.txt"

    result = service.create_empty_classifier(CreateEmptyClassifierOptions(classifier_file=classifier))

    assert result.classifier_file == classifier
    assert result.num_features == 0
    assert classifier.read_text(encoding="utf-8") == service.EMPTY_CLASSIFIER + "\n"
