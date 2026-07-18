from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchBudget:
    max_num_states: int | None
    max_time_seconds: float | None


EXECUTE_SEARCH_BUDGET = SearchBudget(max_num_states=None, max_time_seconds=None)
PROVE_SEARCH_BUDGET = SearchBudget(max_num_states=100_000, max_time_seconds=5.0)
PLAN_TRACE_BUDGET = SearchBudget(max_num_states=1_000_000, max_time_seconds=10.0)
CLASSIFIER_PROOF_BUDGET = SearchBudget(max_num_states=1_000_000, max_time_seconds=None)
CLASSIFIER_MISTAKE_LIMIT = 5
STRUCTURAL_TERMINATION_MAX_FEATURES = 10
STRUCTURAL_TERMINATION_USE_INCOMPLETE_PREPROCESSING = True
