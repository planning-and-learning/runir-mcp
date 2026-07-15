from __future__ import annotations

from enum import StrEnum


class AtomKind(StrEnum):
    FLUENT = "fluent_atoms"
    DERIVED = "derived_atoms"
    STATIC = "static_atoms"


class CandidateSource(StrEnum):
    EMPTY = "empty"
    FILE = "file"


class CounterexampleKind(StrEnum):
    CYCLE = "cycle"
    OPEN_STATE = "open_state"
    DEADEND = "deadend"


class DumpFormat(StrEnum):
    JSON = "json"
    PSV = "psv"
    MD = "md"


class Flag(StrEnum):
    INIT = "init"
    GOAL = "goal"
    OPEN = "open"
    WITNESS = "witness"
    CYCLE = "cycle"
    DEADEND = "deadend"


class HeuristicSentinel(StrEnum):
    DEADEND = "inf"
    UNKNOWN = ""



class RunStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class RunCategory(StrEnum):
    SUCCESS = "success"
    OUT_OF_MEMORY = "out_of_memory"
    OUT_OF_STATES = "out_of_states"
    OUT_OF_TIME = "out_of_time"
    COUNTEREXAMPLE = "counterexample"


class RunItemCategory(StrEnum):
    SUCCESS = "success"
    CYCLE = "cycle"
    OPEN_STATE = "open_state"
    DEADEND = "deadend"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    STRUCTURAL_TERMINATION = "structural_termination"


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    OUT_OF_MEMORY = "out_of_memory"
    OUT_OF_STATES = "out_of_states"
    OUT_OF_TIME = "out_of_time"


class ValidationKind(StrEnum):
    BASE_FIND_SOLUTION = "base_find_solution"
    BASE_TERMINATION = "base_termination"
    EXT_FIND_SOLUTION = "ext_find_solution"
    EXT_TERMINATION = "ext_termination"
    UNS_PROVE = "uns_prove"


class ValidationStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class IncompleteTerminationStatus(StrEnum):
    PROVED = "proved"
    INSUFFICIENT = "insufficient"
    DISABLED = "disabled"


class VariableKind(StrEnum):
    CONCEPT = "concept"
    BOOLEAN = "boolean"
    NUMERICAL = "numerical"
