from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProvePolicyOptions:
    domain_file: str
    problem_file: str
    sketch_file: str
    output_dir: str
    classifier_file: str | None = None
    num_threads: int = 1
    max_num_states: int = 100_000
    max_time_seconds: float = 5.0
    hstar_max_num_states: int = 100_000
    hstar_max_time_seconds: float = 1.0
    include_hstar: bool = True
    include_hlmcut: bool = True
    max_open_state_counterexamples: int = 1
    max_deadend_transition_counterexamples: int = 1
