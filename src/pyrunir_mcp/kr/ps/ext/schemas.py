from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProveModuleProgramOptions:
    domain: str
    train_dir: str
    module_program_file: str
    output_dir: str
    num_threads: int = 1
    max_num_states: int = 100_000
    max_time_seconds: float = 5.0
    max_arity: int = 0
    dump_state_mode: str = "summary"
