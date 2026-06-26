from __future__ import annotations


def test_prove_classifier_accepts_frozen_options(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from pyrunir_mcp.kr.uns import service
    from pyrunir_mcp.kr.uns.schemas import ProveClassifierOptions

    domain = tmp_path / "domain.pddl"
    classifier = tmp_path / "classifier.txt"
    output = tmp_path / "out"
    domain.write_text("(define (domain d))\n", encoding="utf-8")
    classifier.write_text('(:classifier (:symbol c0) (:features) (:expression (or)))\n', encoding="utf-8")

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

    from pyrunir.kr.uns.dl import ClassifierFactory

    assert result.classifier_file == classifier
    assert result.num_features == 0
    assert classifier.read_text(encoding="utf-8") == ClassifierFactory.create_empty_description() + "\n"
