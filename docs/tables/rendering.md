# Table Rendering

Structured artifacts are built once as logical tables, or as sectioned documents with `@key value` headers plus named tables, and rendered through `pyrunir_mcp.tables`.

## Formats

- `.psv`: compact pipe-delimited text, intended as the canonical LLM-facing format.
- `.md`: the same logical tables as aligned Markdown.
- `.json`: the same logical tables as JSON records.

The emitted renderings are selected by `dump_result(..., formats=...)`.

## PSV Conventions

- Tables are pipe-separated with one header row naming the columns.
- PSV tables have no Markdown alignment row.
- Cells are joined by `|` with no surrounding padding.
- A `|` never appears inside a cell.
- Cells never contain newlines; multi-line action strings are reduced to their first line.
- Header lines carry scalar metadata as `@key value`, one per line, before any table.
- The header value is the opaque remainder of the line.
- Boolean values render as `T`/`F`; JSON uses native `true`/`false`.
- Numeric values render as integers.
- Empty optional values render as empty cells.

## Sectioned Documents

Witness, witness-trace, and successor artifacts are sectioned documents:

```text
@tool runir.ps.find_solution
@id cycle-001
@category cycle

[states]
state_id|flags
s0|init
```

In JSON, a sectioned document is one object with headers and sections separated:

```json
{"header": {"tool": "runir.ps.find_solution"}, "sections": {"states": [{"id": "s0", "flags": "init"}]}}
```

## Interned Aliases

Recurring symbols are interned in run-global dictionary tables under `dicts/` and referenced from witness, witness-trace, successor, and index tables by short aliases such as `fK`, `rK`, `aK`, `pK`, `MK`, `mK`, or `vK`.

The alias is always the dictionary row's `id` value.
