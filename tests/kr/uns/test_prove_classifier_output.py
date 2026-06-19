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
                "state_id": 12,
                "predicted_unsolvable": True,
                "actually_solvable": True,
                "feature_values": {"deadend_like": True},
                "fluent_facts": ["(at truck loc1)"],
            },
            {
                "task": "p-003.pddl",
                "category": "false_negative",
                "state_id": 13,
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
    assert fp_item["trace_path"] == "traces/false_positive/false_positive-001.json"
    assert fn_item["trace_path"] == "traces/false_negative/false_negative-002.json"
    assert fp_item["trace_available"] is True
    assert fn_item["trace_available"] is True
    fp = read_json(run_dir / fp_item["path"])
    fn = read_json(run_dir / fn_item["path"])
    fp_trace = read_json(run_dir / fp_item["trace_path"])
    fn_trace = read_json(run_dir / fn_item["trace_path"])
    assert fp["trace_path"] == fp_item["trace_path"]
    assert fn["trace_path"] == fn_item["trace_path"]
    assert fp_trace["feature_values"] == {"deadend_like": True}
    assert fn_trace["feature_values"] == {"deadend_like": False}


def test_prove_classifier_accepts_frozen_options(monkeypatch, tmp_path):
    from pyrunir_mcp.kr.uns import service
    from pyrunir_mcp.kr.uns.schemas import ProveClassifierOptions

    domain = tmp_path / "domain.pddl"
    train = tmp_path / "train"
    output = tmp_path / "out"
    domain.write_text("(define (domain d))\n", encoding="utf-8")
    train.mkdir()

    descriptions = []

    def fake_parse(description, _domain, _repo):
        descriptions.append(description)
        return object()

    monkeypatch.setattr(service, "_repositories", lambda _domain: (object(), object()))
    monkeypatch.setattr(service, "parse_classifier", fake_parse)
    monkeypatch.setattr(service, "get_problem_paths", lambda _train: [])

    result = service.prove_classifier(
        ProveClassifierOptions(
            domain=str(domain),
            train_dir=str(train),
            output_dir=str(output),
            classifier_file=None,
            max_time_seconds=0.01,
        )
    )

    assert descriptions == [service.EMPTY_CLASSIFIER]
    assert result["status"] == "success"
    assert result["primary"]["successful"] is True


def test_reformat_classifier_can_create_empty_classifier(monkeypatch, tmp_path):
    from pyrunir_mcp.kr.uns.reformat import service
    from pyrunir_mcp.kr.uns.reformat.service import ReformatClassifierOptions

    domain = tmp_path / "domain.pddl"
    classifier = tmp_path / "classifier.txt"
    domain.write_text("(define (domain d))\n", encoding="utf-8")

    class Parsed:
        def get_features(self):
            return []

        def __str__(self):
            return service.EMPTY_CLASSIFIER

    descriptions = []

    def fake_parse(description, _domain, _repo):
        descriptions.append(description)
        return Parsed()

    monkeypatch.setattr(service, "_repositories", lambda _domain: (object(), object()))
    monkeypatch.setattr(service, "parse_classifier", fake_parse)

    result = service.reformat_classifier(
        ReformatClassifierOptions(domain_path=domain, classifier_file=classifier, create_empty=True)
    )

    assert result.classifier_file == classifier
    assert result.num_features == 0
    assert descriptions == [service.EMPTY_CLASSIFIER + "\n"]
    assert classifier.read_text(encoding="utf-8") == service.EMPTY_CLASSIFIER + "\n"
