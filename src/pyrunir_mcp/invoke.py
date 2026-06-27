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
from pyrunir_mcp.kr.ps.base.reformat.service import CreateEmptyPolicyOptions, ReformatPolicyOptions as BaseReformatOptions
from pyrunir_mcp.kr.ps.base.reformat.service import create_empty_policy as create_empty_base_policy
from pyrunir_mcp.kr.ps.base.reformat.service import reformat_policy as reformat_base_policy
from pyrunir_mcp.kr.ps.base.schemas import ProvePolicyOptions
from pyrunir_mcp.kr.ps.base.service import prove_policy
from pyrunir_mcp.kr.ps.ext.execute.service import ExecutePolicyOptions as ExtExecuteOptions
from pyrunir_mcp.kr.ps.ext.execute.service import execute_policy as execute_ext_policy
from pyrunir_mcp.kr.ps.ext.reformat.service import CreateEmptyPolicyOptions as ExtCreateEmptyPolicyOptions
from pyrunir_mcp.kr.ps.ext.reformat.service import ReformatModuleOptions, ReformatModuleProgramOptions
from pyrunir_mcp.kr.ps.ext.reformat.service import create_empty_policy as create_empty_ext_policy
from pyrunir_mcp.kr.ps.ext.reformat.service import reformat_module, reformat_module_program
from pyrunir_mcp.kr.ps.ext.schemas import ProveModuleProgramOptions
from pyrunir_mcp.kr.ps.ext.service import prove_module_program
from pyrunir_mcp.kr.ps.ext.termination.schemas import ProveTerminationOptions
from pyrunir_mcp.kr.ps.ext.termination.service import prove_termination
from pyrunir_mcp.kr.uns.reformat.service import CreateEmptyClassifierOptions, ReformatClassifierOptions
from pyrunir_mcp.kr.uns.reformat.service import create_empty_classifier, reformat_classifier
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


def _base_prove(args: Args) -> ToolResult:
    return prove_policy(
        ProvePolicyOptions(
            domain_file=args.string("domain_file"),
            problem_file=args.string("problem_file"),
            sketch_file=args.string("sketch_file"),
            output_dir=args.string("output_dir"),
            num_threads=args.integer("num_threads", 1),
            max_num_states=args.integer("max_num_states", 100_000),
            max_time_seconds=args.number("max_time_seconds", 5.0),
            hstar_max_num_states=args.integer("hstar_max_num_states", 100_000),
            hstar_max_time_seconds=args.number("hstar_max_time_seconds", 1.0),
            include_hstar=args.boolean("include_hstar", True),
            include_hlmcut=args.boolean("include_hlmcut", True),
            max_open_state_counterexamples=args.integer("max_open_state_counterexamples", 1),
            max_deadend_transition_counterexamples=args.integer("max_deadend_transition_counterexamples", 1),
        )
    )


def _ext_prove(args: Args) -> ToolResult:
    return prove_module_program(
        ProveModuleProgramOptions(
            domain_file=args.string("domain_file"),
            problem_file=args.string("problem_file"),
            module_program_file=args.string("module_program_file"),
            output_dir=args.string("output_dir"),
            num_threads=args.integer("num_threads", 1),
            max_num_states=args.integer("max_num_states", 100_000),
            max_time_seconds=args.number("max_time_seconds", 5.0),
            hstar_max_num_states=args.integer("hstar_max_num_states", 100_000),
            hstar_max_time_seconds=args.number("hstar_max_time_seconds", 1.0),
            include_hstar=args.boolean("include_hstar", True),
            include_hlmcut=args.boolean("include_hlmcut", True),
            max_arity=args.integer("max_arity", 0),
            max_open_state_counterexamples=args.integer("max_open_state_counterexamples", 1),
            max_deadend_transition_counterexamples=args.integer("max_deadend_transition_counterexamples", 1),
        )
    )


def _base_reformat(args: Args) -> ToolResult:
    result = reformat_base_policy(
        BaseReformatOptions(
            domain_path=args.path("domain_file"),
            sketch_file=args.path("sketch_file"),
        )
    )
    return reformat_result(
        tool="runir.ps.base.reformat_policy",
        path_key="sketch_file",
        path=result.sketch_file,
        kind=result.kind,
    )


def _base_create_empty(args: Args) -> ToolResult:
    result = create_empty_base_policy(
        CreateEmptyPolicyOptions(
            domain_path=args.path("domain_file"),
            sketch_file=args.path("sketch_file"),
        )
    )
    return reformat_result(
        tool="runir.ps.base.create_empty_policy",
        path_key="sketch_file",
        path=result.sketch_file,
        kind=result.kind,
    )


def _ext_reformat_module_program(args: Args) -> ToolResult:
    result = reformat_module_program(
        ReformatModuleProgramOptions(
            domain_path=args.path("domain_file"),
            module_program_file=args.path("module_program_file"),
        )
    )
    return reformat_result(
        tool="runir.ps.ext.reformat_module_program",
        path_key="module_program_file",
        path=result.path,
        kind=result.kind,
    )


def _ext_reformat_module(args: Args) -> ToolResult:
    result = reformat_module(
        ReformatModuleOptions(
            domain_path=args.path("domain_file"),
            module_file=args.path("module_file"),
        )
    )
    return reformat_result(
        tool="runir.ps.ext.reformat_module",
        path_key="module_file",
        path=result.path,
        kind=result.kind,
    )


def _ext_create_empty(args: Args) -> ToolResult:
    result = create_empty_ext_policy(
        ExtCreateEmptyPolicyOptions(
            module_program_file=args.path("module_program_file"),
        )
    )
    return reformat_result(
        tool="runir.ps.ext.create_empty_module_program",
        path_key="module_program_file",
        path=result.path,
        kind=result.kind,
    )


def _uns_reformat(args: Args) -> ToolResult:
    result = reformat_classifier(
        ReformatClassifierOptions(
            domain_path=args.path("domain_file"),
            classifier_file=args.path("classifier_file"),
        )
    )
    return reformat_result(
        tool="runir.uns.reformat_classifier",
        path_key="classifier_file",
        path=result.classifier_file,
        num_features=result.num_features,
    )


def _base_execute(args: Args) -> ToolResult:
    output_dir = fresh_output_dir(args.path("output_dir"))
    result = execute_base_policy(
        BaseExecuteOptions(
            domain_file=args.path("domain_file"),
            problem_file=args.path("problem_file"),
            sketch_file=args.path("sketch_file"),
            num_threads=args.integer("num_threads", 1),
            random_seed=args.integer("random_seed", 0),
            random_seed_start=args.integer("random_seed_start", 0),
            num_rollouts=args.integer("num_rollouts", 1),
            shuffle_labeled_succ_nodes=args.boolean("shuffle_labeled_succ_nodes", True),
            max_arity=args.integer("max_arity", 0),
            max_num_states=args.optional_integer("max_num_states"),
            max_time_seconds=args.optional_number("max_time_seconds"),
            hstar_max_num_states=args.integer("hstar_max_num_states", 100_000),
            hstar_max_time_seconds=args.number("hstar_max_time_seconds", 1.0),
            include_hstar=args.boolean("include_hstar", True),
            include_hlmcut=args.boolean("include_hlmcut", True),
            dump_dir=output_dir,
        )
    )
    return execute_result(tool="runir.ps.base.execute_policy", result=result, output_dir=output_dir)


def _ext_execute(args: Args) -> ToolResult:
    output_dir = fresh_output_dir(args.path("output_dir"))
    result = execute_ext_policy(
        ExtExecuteOptions(
            domain_file=args.path("domain_file"),
            problem_file=args.path("problem_file"),
            module_program_file=args.path("module_program_file"),
            num_threads=args.integer("num_threads", 1),
            random_seed=args.integer("random_seed", 0),
            random_seed_start=args.integer("random_seed_start", 0),
            num_rollouts=args.integer("num_rollouts", 1),
            shuffle_labeled_succ_nodes=args.boolean("shuffle_labeled_succ_nodes", True),
            max_arity=args.integer("max_arity", 0),
            max_num_states=args.optional_integer("max_num_states"),
            max_time_seconds=args.optional_number("max_time_seconds"),
            hstar_max_num_states=args.integer("hstar_max_num_states", 100_000),
            hstar_max_time_seconds=args.number("hstar_max_time_seconds", 1.0),
            include_hstar=args.boolean("include_hstar", True),
            include_hlmcut=args.boolean("include_hlmcut", True),
            dump_dir=output_dir,
        )
    )
    return execute_result(tool="runir.ps.ext.execute_module_program", result=result, output_dir=output_dir)


def _uns_create_empty(args: Args) -> ToolResult:
    result = create_empty_classifier(
        CreateEmptyClassifierOptions(classifier_file=args.path("classifier_file"))
    )
    return reformat_result(
        tool="runir.uns.create_empty_classifier",
        path_key="classifier_file",
        path=result.classifier_file,
        num_features=result.num_features,
    )


def _termination(args: Args) -> ToolResult:
    return prove_termination(
        ProveTerminationOptions(
            domain_file=args.string("domain_file"),
            module_program_file=args.string("module_program_file"),
            output_dir=args.string("output_dir"),
        )
    )


def _uns_prove(args: Args) -> ToolResult:
    return prove_classifier(
        ProveClassifierOptions(
            domain_file=args.string("domain_file"),
            problem_file=args.string("problem_file"),
            output_dir=args.string("output_dir"),
            classifier_file=args.optional_string("classifier_file"),
            max_num_states=args.integer("max_num_states", 100_000),
            max_time_seconds=args.number("max_time_seconds", 1_000_000_000.0),
        )
    )


TOOLS: dict[str, ToolHandler] = {
    "runir.ps.base.prove_policy": _base_prove,
    "runir.ps.base.execute_policy": _base_execute,
    "runir.ps.base.create_empty_policy": _base_create_empty,
    "runir.ps.base.reformat_policy": _base_reformat,
    "runir.ps.ext.prove_module_program": _ext_prove,
    "runir.ps.ext.execute_module_program": _ext_execute,
    "runir.ps.ext.create_empty_module_program": _ext_create_empty,
    "runir.ps.ext.reformat_module_program": _ext_reformat_module_program,
    "runir.ps.ext.reformat_module": _ext_reformat_module,
    "runir.ps.ext.prove_termination": _termination,
    "runir.uns.create_empty_classifier": _uns_create_empty,
    "runir.uns.prove_classifier": _uns_prove,
    "runir.uns.reformat_classifier": _uns_reformat,
}


def _write_result_json(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fh:
        fh.write(rendered)


_OFFSET_RE = re.compile(r"\bat offset (\d+)\b")


def _source_path_from_args(args: Args) -> Path | None:
    for key in ("sketch_file", "module_program_file", "module_file", "classifier_file"):
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


def _format_tool_error(tool: str, args: Args, exc: BaseException) -> tuple[ToolResult, str]:
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
