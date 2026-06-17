from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProveSketchPolicyOptions:
    domain: str
    train_dir: str
    output_dir: str
    policy_file: str | None = None
    num_threads: int = 1
    max_num_states: int = 100_000
    max_time_seconds: float = 5.0
    dump_state_mode: str = "summary"
