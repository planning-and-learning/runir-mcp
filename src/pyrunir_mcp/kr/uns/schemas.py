from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProveClassifierOptions:
    domain_file: str
    problem_file: str
    output_dir: str
    classifier_file: str
    max_num_states: int = 1_000_000
    max_time_seconds: float = 1_000_000_000.0
    max_false_positive_counterexamples: int = 20
    max_false_negative_counterexamples: int = 20
