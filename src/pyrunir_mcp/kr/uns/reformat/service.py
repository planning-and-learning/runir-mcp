from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLRepositoryFactory
from pyrunir.kr.uns import RepositoryFactory
from pyrunir.kr.uns.dl import parse_classifier
from pytyr.formalism.planning import Parser


EMPTY_CLASSIFIER = '(:classifier (:symbol c0) (:description "") (:features) (:expression (or)))'


@dataclass(frozen=True)
class ReformatClassifierOptions:
    domain_path: Path
    classifier_file: Path
    create_empty: bool = False


@dataclass(frozen=True)
class ReformatClassifierResult:
    classifier_file: Path
    num_features: int


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = UnsDLRepositoryFactory().create(planning_domain)
    classifier_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, classifier_repository


def reformat_classifier(options: ReformatClassifierOptions) -> ReformatClassifierResult:
    planning_domain, repository = _repositories(options.domain_path)
    if options.create_empty and not options.classifier_file.exists():
        options.classifier_file.parent.mkdir(parents=True, exist_ok=True)
        with options.classifier_file.open("x", encoding="utf-8") as fh:
            fh.write(EMPTY_CLASSIFIER + "\n")
    text = options.classifier_file.read_text(encoding="utf-8")
    classifier = parse_classifier(text, planning_domain, repository)
    options.classifier_file.write_text(f"{classifier}\n", encoding="utf-8")
    return ReformatClassifierResult(
        classifier_file=options.classifier_file,
        num_features=len(list(classifier.get_features())),
    )
