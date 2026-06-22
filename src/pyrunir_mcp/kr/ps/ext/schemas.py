from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProveModuleProgramOptions:
    domain_file: str
    problem_file: str
    module_program_file: str
    output_dir: str
    num_threads: int = 1
    max_num_states: int = 100_000
    max_time_seconds: float = 5.0
    max_open_state_counterexamples: int = 1
    max_deadend_transition_counterexamples: int = 1
    max_arity: int = 0
