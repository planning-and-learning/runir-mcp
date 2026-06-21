from __future__ import annotations

import argparse
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from collections.abc import Callable
from typing import TypeAlias

from pyrunir_mcp.kr.ps.base.execute.service import ExecutePolicyOptions as BaseExecuteOptions
from pyrunir_mcp.kr.ps.base.execute.service import execute_policy as execute_base_policy
from pyrunir_mcp.kr.ps.base.reformat.service import ReformatPolicyOptions as BaseReformatOptions
from pyrunir_mcp.kr.ps.base.reformat.service import reformat_policy as reformat_base_policy
from pyrunir_mcp.kr.ps.base.schemas import ProveSketchPolicyOptions
from pyrunir_mcp.kr.ps.base.service import prove_sketch_policy
from pyrunir_mcp.kr.ps.ext.execute.service import ExecutePolicyOptions as ExtExecuteOptions
from pyrunir_mcp.kr.ps.ext.execute.service import execute_policy as execute_ext_policy
from pyrunir_mcp.kr.ps.ext.reformat.service import ReformatPolicyOptions as ExtReformatOptions
from pyrunir_mcp.kr.ps.ext.reformat.service import reformat_policy as reformat_ext_policy
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.kr.ps.ext.service import prove_module_program
from pyrunir_mcp.kr.ps.ext.termination.schemas import ProveTerminationOptions
from pyrunir_mcp.kr.ps.ext.termination.service import prove_termination
from pyrunir_mcp.kr.uns.reformat.service import ReformatClassifierOptions
from pyrunir_mcp.kr.uns.reformat.service import reformat_classifier
from pyrunir_mcp.kr.uns.schemas import ProveClassifierOptions
from pyrunir_mcp.kr.uns.service import prove_classifier
from pyrunir_mcp.artifacts import fresh_output_dir
from pyrunir_mcp.json_types import JsonObject, JsonValue
from pyrunir_mcp.results import execute_result, reformat_result
from pyrunir_mcp.roles import load_role


ToolResult: TypeAlias = JsonObject


class Args:
    def __init__(self, values: JsonObject) -> None:
        self.values = values

    def value(self, key: str, default: JsonValue | None = None) -> JsonValue | None:
        return self.values[key] if key in self.values else default

    def string(self, key: str, default: str | None = None) -> str:
        value = self.value(key, default)
        if not isinstance(value, str):
            raise TypeError(f"{key} must be a string")
        return value

    def optional_string(self, key: str) -> str | None:
        value = self.value(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{key} must be a string or null")
        return value

    def integer(self, key: str, default: int) -> int:
        value = self.value(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{key} must be an integer")
        return value

    def optional_integer(self, key: str) -> int | None:
        value = self.value(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{key} must be an integer or null")
        return value

    def number(self, key: str, default: float) -> float:
        value = self.value(key, default)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"{key} must be a number")
        return float(value)

    def number_alias(self, key: str, alias: str, default: float) -> float:
        return self.number(key, default) if key in self.values else self.number(alias, default)

    def optional_number(self, key: str) -> float | None:
        value = self.value(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"{key} must be a number or null")
        return float(value)

    def boolean(self, key: str, default: bool) -> bool:
        value = self.value(key, default)
        if not isinstance(value, bool):
            raise TypeError(f"{key} must be a boolean")
        return value

    def path(self, key: str) -> Path:
        return Path(self.string(key)).resolve()


ToolHandler: TypeAlias = Callable[[Args], ToolResult]


def _args(args: Args | JsonObject) -> Args:
    return args if isinstance(args, Args) else Args(args)


def _base_prove(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    return prove_sketch_policy(
        ProveSketchPolicyOptions(
            domain=args.string("domain"),
            train_dir=args.string("train_dir"),
            output_dir=args.string("output_dir"),
            policy_file=args.optional_string("policy_file"),
            num_threads=args.integer("num_threads", 1),
            max_num_states=args.integer("max_num_states", 100_000),
            max_time_seconds=args.number_alias("max_time_seconds", "max_time", 5.0),
            dump_state_mode=args.string("dump_state_mode", "summary"),
        )
    )


def _ext_prove(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    return prove_module_program(
        ProveModuleProgramOptions(
            domain=args.string("domain"),
            train_dir=args.string("train_dir"),
            module_program_file=args.string("module_program_file"),
            output_dir=args.string("output_dir"),
            num_threads=args.integer("num_threads", 1),
            max_num_states=args.integer("max_num_states", 100_000),
            max_time_seconds=args.number_alias("max_time_seconds", "max_time", 5.0),
            max_arity=args.integer("max_arity", 0),
            dump_state_mode=args.string("dump_state_mode", "summary"),
        )
    )


def _base_reformat(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    result = reformat_base_policy(
        BaseReformatOptions(
            domain_path=args.path("domain"),
            policy_file=args.path("policy_file"),
            kind=args.string("kind", "auto"),
            create_empty=args.boolean("create_empty", False),
        )
    )
    return reformat_result(
        tool="runir.ps.base.reformat_policy",
        path_key="policy_file",
        path=result.policy_file,
        kind=result.kind,
    )


def _ext_reformat(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    result = reformat_ext_policy(
        ExtReformatOptions(
            domain_path=args.path("domain"),
            policy_file=Path(args.optional_string("policy_file") or args.string("module_program_file")).resolve(),
            kind=args.string("kind", "auto"),
        )
    )
    return reformat_result(
        tool="runir.ps.ext.reformat_module_program",
        path_key="policy_file",
        path=result.policy_file,
        kind=result.kind,
    )


def _uns_reformat(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    result = reformat_classifier(
        ReformatClassifierOptions(
            domain_path=args.path("domain"),
            classifier_file=args.path("classifier_file"),
            create_empty=args.boolean("create_empty", False),
        )
    )
    return reformat_result(
        tool="runir.uns.reformat_classifier",
        path_key="classifier_file",
        path=result.classifier_file,
        num_features=result.num_features,
    )


def _base_execute(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    output_dir = fresh_output_dir(args.path("output_dir"))
    result = execute_base_policy(
        BaseExecuteOptions(
            domain_path=args.path("domain"),
            problem_dir=args.path("problem_dir"),
            policy_file=args.path("policy_file"),
            num_threads=args.integer("num_threads", 1),
            random_seed=args.integer("random_seed", 0),
            random_seed_start=args.integer("random_seed_start", 0),
            num_rollouts=args.integer("num_rollouts", 1),
            shuffle_labeled_succ_nodes=args.boolean("shuffle_labeled_succ_nodes", True),
            max_arity=args.integer("max_arity", 0),
            max_num_states=args.optional_integer("max_num_states"),
            max_time=args.optional_number("max_time"),
            dump_dir=output_dir,
            dump_state_mode=args.string("dump_state_mode", "summary"),
            dump_max_steps=args.optional_integer("dump_max_steps"),
            dump_max_compatible_actions=args.optional_integer("dump_max_compatible_actions"),
            dump_max_states=args.optional_integer("dump_max_states"),
            audit_compatible_successors=args.boolean("audit_compatible_successors", False),
            classify_compatible_successors=args.boolean("classify_compatible_successors", False),
            classifier=args.string("classifier", "astar"),
            classifier_max_time=args.number("classifier_max_time", 1.0),
            classifier_max_states=args.integer("classifier_max_states", 10_000),
            include_policy_metadata=args.boolean("include_policy_metadata", False),
            replay_trace=None if args.optional_string("replay_trace") is None else args.path("replay_trace"),
        )
    )
    return execute_result(tool="runir.ps.base.execute_policy", result=result, output_dir=output_dir)


def _ext_execute(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    output_dir = fresh_output_dir(args.path("output_dir"))
    result = execute_ext_policy(
        ExtExecuteOptions(
            domain_path=args.path("domain"),
            problem_dir=args.path("problem_dir"),
            module_program_file=args.path("module_program_file"),
            num_threads=args.integer("num_threads", 1),
            random_seed=args.integer("random_seed", 0),
            random_seed_start=args.integer("random_seed_start", 0),
            num_rollouts=args.integer("num_rollouts", 1),
            shuffle_labeled_succ_nodes=args.boolean("shuffle_labeled_succ_nodes", True),
            max_arity=args.integer("max_arity", 0),
            max_num_states=args.optional_integer("max_num_states"),
            max_time=args.optional_number("max_time"),
            dump_dir=output_dir,
            dump_state_mode=args.string("dump_state_mode", "summary"),
            dump_max_steps=args.optional_integer("dump_max_steps"),
            dump_max_compatible_actions=args.optional_integer("dump_max_compatible_actions"),
            dump_max_states=args.optional_integer("dump_max_states"),
            audit_compatible_successors=args.boolean("audit_compatible_successors", False),
            classify_compatible_successors=args.boolean("classify_compatible_successors", False),
            classifier=args.string("classifier", "astar"),
            classifier_max_time=args.number("classifier_max_time", 1.0),
            classifier_max_states=args.integer("classifier_max_states", 10_000),
            include_policy_metadata=args.boolean("include_policy_metadata", False),
            replay_trace=None if args.optional_string("replay_trace") is None else args.path("replay_trace"),
        )
    )
    return execute_result(tool="runir.ps.ext.execute_module_program", result=result, output_dir=output_dir)


def _termination(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    return prove_termination(
        ProveTerminationOptions(
            domain=args.string("domain"),
            module_program_file=args.string("module_program_file"),
            output_dir=args.string("output_dir"),
        )
    )


def _uns_prove(args: Args | JsonObject) -> ToolResult:
    args = _args(args)
    return prove_classifier(
        ProveClassifierOptions(
            domain=args.string("domain"),
            train_dir=args.string("train_dir"),
            output_dir=args.string("output_dir"),
            classifier_file=args.optional_string("classifier_file"),
            max_num_states=args.integer("max_num_states", 100_000),
            max_time_seconds=args.number_alias("max_time_seconds", "max_time", 5.0),
        )
    )


TOOLS: dict[str, ToolHandler] = {
    "runir.ps.base.prove_sketch_policy": _base_prove,
    "runir.ps.base.execute_policy": _base_execute,
    "runir.ps.base.reformat_policy": _base_reformat,
    "runir.ps.ext.prove_module_program": _ext_prove,
    "runir.ps.ext.execute_module_program": _ext_execute,
    "runir.ps.ext.reformat_module_program": _ext_reformat,
    "runir.ps.ext.prove_termination": _termination,
    "runir.uns.prove_classifier": _uns_prove,
    "runir.uns.reformat_classifier": _uns_reformat,
}


def _write_result_json(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        fh.write(rendered)


_OFFSET_RE = re.compile(r"\bat offset (\d+)\b")


def _source_path_from_args(args: Args | JsonObject) -> Path | None:
    args = _args(args)
    for key in ("policy_file", "module_program_file", "classifier_file"):
        value = args.value(key)
        if value:
            return Path(str(value))
    return None


def _source_excerpt(path: Path | None, message: str) -> JsonObject | None:
    match = _OFFSET_RE.search(message)
    if path is None or match is None:
        return None
    try:
        offset = int(match.group(1))
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    offset = max(0, min(offset, len(text)))
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", offset)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    line_no = text.count("\n", 0, offset) + 1
    column = offset - line_start + 1
    return {
        "path": path.as_posix(),
        "offset": offset,
        "line": line_no,
        "column": column,
        "source_line": line,
        "pointer": " " * max(column - 1, 0) + "^",
    }


def _format_tool_error(tool: str, args: Args | JsonObject, exc: BaseException) -> tuple[ToolResult, str]:
    args = _args(args)
    error_type = type(exc).__name__
    message = str(exc)
    source = _source_excerpt(_source_path_from_args(args), message)
    result: ToolResult = {
        "status": "error",
        "primary": {
            "successful": False,
            "category": "tool_error",
            "error_type": error_type,
            "message": message,
        },
        "summary": {
            "tool": tool,
            "status": "error",
            "error_type": error_type,
            "message": message,
        },
        "items": [],
    }
    lines = [f"{tool} failed: {error_type}: {message}"]
    if source is not None:
        result["primary"]["source"] = source
        result["summary"]["source"] = source
        lines.extend(
            [
                f"{source['path']}:{source['line']}:{source['column']}",
                str(source["source_line"]),
                str(source["pointer"]),
            ]
        )
    return result, "\n".join(lines) + "\n"


def _ensure_tool_allowed(tool_name: str) -> None:
    role = load_role()
    if role.allows(tool_name):
        return
    allowed = ", ".join(sorted(role.allowed_tools))
    raise PermissionError(
        f"{tool_name} is not allowed for PYRUNIR_MCP_ROLE={role.name}; "
        f"allowed tools: {allowed}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke a pyrunir-mcp tool with JSON arguments.")
    parser.add_argument("tool", choices=sorted(TOOLS))
    parser.add_argument("--args-json", required=True)
    parser.add_argument("--result-json")
    parsed = parser.parse_args()
    try:
        _ensure_tool_allowed(parsed.tool)
    except (PermissionError, ValueError) as exc:
        parser.error(str(exc))
    args = json.loads(parsed.args_json)
    if not isinstance(args, dict):
        raise TypeError("--args-json must decode to an object")
    tool_args = Args(args)
    captured_stdout = io.StringIO()
    try:
        with redirect_stdout(captured_stdout):
            result = TOOLS[parsed.tool](tool_args)
    except Exception as exc:
        tool_stdout = captured_stdout.getvalue()
        result, rendered_error = _format_tool_error(parsed.tool, tool_args, exc)
        if tool_stdout:
            result["_tool_stdout"] = tool_stdout
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if parsed.result_json:
            result_path = Path(parsed.result_json).resolve()
            _write_result_json(result_path, rendered)
        else:
            print(rendered, end="")
        sys.stderr.write(rendered_error)
        raise SystemExit(1) from None
    tool_stdout = captured_stdout.getvalue()
    if tool_stdout:
        result = {**result, "_tool_stdout": tool_stdout}
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if parsed.result_json:
        result_path = Path(parsed.result_json).resolve()
        _write_result_json(result_path, rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
