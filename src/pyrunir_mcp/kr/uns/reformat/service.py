from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypddl.formalism import ParserOptions
from pyrunir.kr.dl.uns import ConstructorRepositoryFactory as UnsDLRepositoryFactory
from pyrunir.kr.uns import RepositoryFactory
from pyrunir.kr.uns.dl import ClassifierFactory, parse_classifier
from pytyr.formalism.planning import Parser


@dataclass(frozen=True)
class ReformatClassifierOptions:
    domain_path: Path
    classifier_file: Path


@dataclass(frozen=True)
class CreateEmptyClassifierOptions:
    classifier_file: Path


@dataclass(frozen=True)
class ReformatClassifierResult:
    classifier_file: Path
    num_features: int


def _repositories(domain_path: Path):
    planning_domain = Parser(domain_path, ParserOptions()).get_domain()
    dl_repository = UnsDLRepositoryFactory().create(planning_domain)
    classifier_repository = RepositoryFactory().create(dl_repository)
    return planning_domain, classifier_repository


def create_empty_classifier(options: CreateEmptyClassifierOptions) -> ReformatClassifierResult:
    # The empty-classifier template comes from runir's ClassifierFactory (the single source of
    # truth, like base/ext), not a hardcoded string. It is domain-free (no features, empty DNF).
    options.classifier_file.parent.mkdir(parents=True, exist_ok=True)
    options.classifier_file.write_text(ClassifierFactory.create_empty_description() + "\n", encoding="utf-8")
    return ReformatClassifierResult(classifier_file=options.classifier_file, num_features=0)


def reformat_classifier(options: ReformatClassifierOptions) -> ReformatClassifierResult:
    planning_domain, repository = _repositories(options.domain_path)
    text = options.classifier_file.read_text(encoding="utf-8")
    classifier = parse_classifier(text, planning_domain, repository)
    options.classifier_file.write_text(f"{classifier}\n", encoding="utf-8")
    return ReformatClassifierResult(
        classifier_file=options.classifier_file,
        num_features=len(list(classifier.get_features())),
    )
