from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProveClassifierOptions:
    domain: str
    train_dir: str
    output_dir: str
    classifier_file: str | None = None
    max_num_states: int = 1_000_000
    max_time_seconds: float = 1_000_000_000.0
