from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProveTerminationOptions:
    domain_file: str
    module_program_file: str
    output_dir: str
