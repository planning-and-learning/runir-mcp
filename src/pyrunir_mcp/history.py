from __future__ import annotations

from dataclasses import dataclass, field

from pyrunir_mcp.validation import ValidationObservation


def _same_observation_key(left: ValidationObservation, right: ValidationObservation) -> bool:
    if left.fingerprint is not None or right.fingerprint is not None:
        return left.fingerprint == right.fingerprint
    return (
        left.kind is right.kind
        and left.status is right.status
        and left.candidate_id == right.candidate_id
        and left.classifier_id == right.classifier_id
    )


@dataclass(frozen=True, slots=True)
class HistoryFeedback:
    observation: ValidationObservation
    previous_occurrences: int
    total_observations: int

    @property
    def repeated(self) -> bool:
        return self.previous_occurrences > 0


@dataclass(slots=True)
class ValidationHistory:
    observations: list[ValidationObservation] = field(default_factory=list)

    def fold(self, observation: ValidationObservation) -> HistoryFeedback:
        previous_occurrences = sum(
            1 for prior in self.observations if _same_observation_key(prior, observation)
        )
        self.observations.append(observation)
        return HistoryFeedback(
            observation=observation,
            previous_occurrences=previous_occurrences,
            total_observations=len(self.observations),
        )
