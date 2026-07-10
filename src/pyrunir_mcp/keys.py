from __future__ import annotations

from enum import StrEnum


class Keys(StrEnum):
    """Keys used in serialized objects, ordered from envelopes to leaf values."""

    # Document envelope.
    HEADER = "header"
    SCHEMA_VERSION = "schema_version"
    SECTIONS = "sections"

    # Run and report envelope.
    TOOL = "tool"
    STATUS = "status"
    SUMMARY = "summary"
    PRIMARY = "primary"
    ARTIFACTS = "artifacts"
    METADATA = "metadata"

    # Record identity and classification.
    ID = "id"
    INDEX = "index"
    KIND = "kind"
    CATEGORY = "category"
    SUBJECT = "subject"
    ORIGIN = "origin"
    SEED = "seed"
    COUNTS = "counts"

    # Execution results.
    ROLLOUTS = "rollouts"
    ROLLOUT_COUNT = "rollout_count"
    TASKS = "tasks"
    FAILURE = "failure"
    FAILURE_SEEDS = "failure_seeds"
    SUCCESS_SEEDS = "success_seeds"
    PROOF = "proof"
    TERMINATION = "termination"
    PROGRAM_STATUS = "program_status"
    STATE_GRAPH_STATUS = "state_graph_status"
    NONTERMINATING_MODULES = "nonterminating_modules"

    # Validation results and observations.
    RESULT_ID = "result_id"
    CONTEXT = "context"
    CANDIDATE = "candidate"
    CANDIDATE_ID = "candidate_id"
    OBSERVATION = "observation"
    OBSERVATIONS = "observations"
    CLASSIFIER_ID = "classifier_id"
    DETAILS = "details"
    SEARCH_BUDGET = "search_budget"
    PLAN_TRACE_BUDGET = "plan_trace_budget"
    MAX_STATE_COUNT = "max_state_count"
    MAX_TIME_SECONDS = "max_time_seconds"
    STATE_COUNT = "state_count"
    UNSOLVABLE_STATE_COUNT = "unsolvable_state_count"
    FALSE_POSITIVE_COUNT = "false_positive_count"
    FALSE_NEGATIVE_COUNT = "false_negative_count"
    COUNTEREXAMPLES = "counterexamples"

    # State and transition data.
    STATES = "states"
    STATE_INDEX = "state_index"
    MODULE = "module"
    MEMORY = "memory"
    IS_INITIAL = "is_initial"
    IS_GOAL = "is_goal"
    IS_UNSOLVABLE = "is_unsolvable"
    HSTAR = "hstar"
    HLMCUT = "hlmcut"
    FEATURE_VALUES = "feature_values"
    FLUENT_ATOMS = "fluent_atoms"
    DERIVED_ATOMS = "derived_atoms"
    ACTION = "action"
    RULE = "rule"

    # Artifact references and filesystem locations.
    FAILURES = "failures"
    SUCCESSES = "successes"
    TRACE = "trace"
    WITNESS = "witness"
    SUCCESSORS = "successors"
    PLAN_TRACE = "plan_trace"
    TASK_FILE = "task_file"
    CANDIDATE_PATH = "candidate_path"
    DOMAIN_PATH = "domain_path"
    GENERATOR_PATH = "generator_path"
    OUTPUT_DIR = "output_dir"
    PLAN_TRACE_PATH = "plan_trace_path"
    SUCCESSORS_PATH = "successors_path"
    TASK_DIR = "task_dir"
    TASK_PATH = "task_path"
    TRACE_PATH = "trace_path"
    WITNESS_PATH = "witness_path"

    # Task generation.
    CONFIG = "config"
    DOMAIN_NAME = "domain_name"
    GENERATED_TASKS = "generated_tasks"
    INVALID_TASKS = "invalid_tasks"
    REASON = "reason"
    SIGNATURE = "signature"
    ERROR = "error"
    ERROR_CATEGORY = "error_category"
    ERROR_TYPE = "error_type"

    # Named sections and dictionary leaf values.
    FACTS = "facts"
    TRANSITIONS = "transitions"
    CYCLE = "cycle"
    PLAN = "plan"
    VERTICES = "vertices"
    EDGES = "edges"
    FEATURES = "features"
    RULES = "rules"
    ACTIONS = "actions"
    ATOMS = "atoms"
    MODULES = "modules"
    VARIABLES = "variables"
    SYMBOL = "symbol"
    ATOM = "atom"


class TableColumns(StrEnum):
    """Columns used only by rendered tables, ordered from states to graph structure."""

    # State and fact tables.
    STATE_ID = "state_id"
    MODULE_ID = "module_id"
    MEMORY_ID = "memory_id"
    FLAGS = "flags"
    ATOM_IDS = "atom_ids"

    # Transition and successor tables.
    STEP = "step"
    SOURCE_STATE_ID = "source_state_id"
    SOURCE_MODULE_ID = "source_module_id"
    SOURCE_MEMORY_ID = "source_memory_id"
    TARGET_STATE_ID = "target_state_id"
    TARGET_MODULE_ID = "target_module_id"
    TARGET_MEMORY_ID = "target_memory_id"
    RULE_ID = "rule_id"
    ACTION_ID = "action_id"
    DELTAS = "deltas"

    # Cycle descriptors.
    VERTEX_INDICES = "vertex_indices"
    EDGE_INDICES = "edge_indices"

    # Structural graph tables.
    VERTEX_INDEX = "vertex_index"
    EDGE_INDEX = "edge_index"
    SOURCE_VERTEX_INDEX = "source_vertex_index"
    TARGET_VERTEX_INDEX = "target_vertex_index"
