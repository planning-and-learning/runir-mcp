# Coding conventions:

- Every parameter needs to be type hinted and strongly typed.

## Pyright

Treat Pyright as a specification of the code's static types. Make the code satisfy the type checker; do not weaken the type checker to satisfy the code.

### Rules

* Keep `pyrightconfig.json` in `strict` mode.
* Keep `include: ["src", "tests"]`.
* Do not relax Pyright diagnostics or configuration.
* Do not add `# pyright: ignore[...]` comments.
* Preserve runtime behavior.

### Fix strategy

When resolving Pyright diagnostics, prefer the following, in order:

1. Add precise type annotations.
2. Refactor into typed helper functions.
3. Introduce appropriate typing constructs (`Protocol`, `TypedDict`, `TypeAlias`, `Literal`, `Final`, generics).
4. Narrow types using control flow (`isinstance`, assertions, pattern matching, etc.).
5. Use `cast(...)` only at explicit dynamic boundaries (e.g. JSON/TOML/YAML parsing, deserialization, plugin loading, or incomplete third-party stubs). Every `cast(...)` must have an obvious local justification.

Never introduce `Any`, unnecessary `cast(...)`, or semantic changes solely to eliminate a type error.

### Acceptance criteria

* `rg "pyright: ignore" src tests` returns no matches.
* `uvx pyright` reports zero errors.
* `.venv/bin/ruff check .` passes.
* `.venv/bin/pytest -q` passes.
* Every remaining `cast(...)` is justified by a dynamic or third-party boundary.
