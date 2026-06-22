from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProveSketchPolicyOptions:
    domain_file: str
    problem_file: str
    sketch_file: str
    output_dir: str
    num_threads: int = 1
    max_num_states: int = 100_000
    max_time_seconds: float = 5.0
