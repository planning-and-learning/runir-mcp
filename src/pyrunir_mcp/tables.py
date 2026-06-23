"""Render one logical artifact to PSV, Markdown, or JSON.

Project output policy (see docs/AGENT.md): JSON only for manifest/machine metadata,
PSV for anything the LLM reads, Markdown only for human summaries. This module is the
single source of truth so a `Table`/`Document` can be emitted in any of the three.

Architecture: the *artifact* is the data (`Table`, `Document`); the *format* is a
`Renderer`. A new section is just a new `Table`/`Document` — every renderer handles it
automatically. A new format is one new `Renderer` subclass plus a registry entry —
nothing else changes. PSV and Markdown table bodies are rendered with jinja2; JSON goes
through ``json.dumps`` (templating JSON would risk escaping bugs).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from jinja2 import DictLoader, Environment

from pyrunir_mcp.json_types import JsonValue

Fmt = Literal["psv", "md", "json"]


@dataclass(frozen=True)
class Table:
    name: str
    columns: list[str]
    rows: list[list[JsonValue]]

    def __post_init__(self) -> None:
        if "\n" in self.name:
            raise ValueError(f"table name must not contain a newline: {self.name!r}")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    f"row has {len(row)} cells, expected {len(self.columns)} "
                    f"({self.columns}): {row!r}"
                )


@dataclass(frozen=True)
class Document:
    """A sectioned artifact: ordered ``@key value`` header lines plus named tables."""

    header: list[tuple[str, str]]
    sections: list[Table]


_TEMPLATES = {
    "psv_table.j2": (
        "{{ columns | join('|') }}\n"
        "{% for row in rows %}{{ row | join('|') }}\n{% endfor %}"
    ),
    "md_table.j2": (
        "| {{ columns | join(' | ') }} |\n"
        "| {{ rules | join(' | ') }} |\n"
        "{% for row in rows %}| {{ row | join(' | ') }} |\n{% endfor %}"
    ),
}

_ENV = Environment(loader=DictLoader(_TEMPLATES), trim_blocks=True, lstrip_blocks=True)


def _scalar(value: JsonValue) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "T" if value else "F"
    return str(value)


def _json_records(table: Table) -> list[dict[str, JsonValue]]:
    return [dict(zip(table.columns, row)) for row in table.rows]


class Renderer(ABC):
    """Renders a logical artifact to one concrete format."""

    @abstractmethod
    def table(self, table: Table) -> str: ...

    @abstractmethod
    def document(self, doc: Document) -> str: ...


class PSVRenderer(Renderer):
    def cell(self, value: JsonValue) -> str:
        text = _scalar(value)
        if "|" in text or "\n" in text:
            raise ValueError(f"PSV cell must not contain '|' or newline: {text!r}")
        return text

    def table(self, table: Table) -> str:
        columns = [self.cell(column) for column in table.columns]
        rows = [[self.cell(value) for value in row] for row in table.rows]
        rendered = _ENV.get_template("psv_table.j2").render(columns=columns, rows=rows)
        return rendered.rstrip("\n")

    def document(self, doc: Document) -> str:
        lines = []
        for key, value in doc.header:
            if "\n" in key or "\n" in str(value):
                raise ValueError(f"PSV header line must not contain a newline: @{key} {value!r}")
            lines.append(f"@{key} {value}")
        header = "\n".join(lines)
        sections = []
        for t in doc.sections:
            if "[" in t.name or "]" in t.name:
                raise ValueError(f"PSV section name must not contain '[' or ']': {t.name!r}")
            sections.append(f"[{t.name}]\n{self.table(t)}")
        return "\n\n".join(([header] if header else []) + sections)


class MarkdownRenderer(Renderer):
    def cell(self, value: JsonValue) -> str:
        return _scalar(value).replace("|", r"\|").replace("\n", " ")

    def table(self, table: Table) -> str:
        columns = [self.cell(column) for column in table.columns]
        cells = [[self.cell(value) for value in row] for row in table.rows]
        widths = [
            max(len(column), 3, *(len(row[index]) for row in cells))
            for index, column in enumerate(columns)
        ]
        rendered = _ENV.get_template("md_table.j2").render(
            columns=[c.ljust(w) for c, w in zip(columns, widths)],
            rules=["-" * w for w in widths],
            rows=[[v.ljust(w) for v, w in zip(row, widths)] for row in cells],
        )
        return rendered.rstrip("\n")

    def document(self, doc: Document) -> str:
        header = "\n".join(f"- **{key}**: {value}" for key, value in doc.header)
        sections = [f"## {t.name}\n\n{self.table(t)}" for t in doc.sections]
        return "\n\n".join(([header] if header else []) + sections)


class JSONRenderer(Renderer):
    def table(self, table: Table) -> str:
        return json.dumps(_json_records(table), indent=2, sort_keys=True)

    def document(self, doc: Document) -> str:
        result = {
            "header": {key: value for key, value in doc.header},
            "sections": {t.name: _json_records(t) for t in doc.sections},
        }
        return json.dumps(result, indent=2, sort_keys=True)


_RENDERERS: dict[str, Renderer] = {
    "psv": PSVRenderer(),
    "md": MarkdownRenderer(),
    "json": JSONRenderer(),
}


def renderer_for(fmt: Fmt) -> Renderer:
    try:
        return _RENDERERS[fmt]
    except KeyError:
        raise ValueError(f"unknown format: {fmt!r}") from None


def render(table: Table, fmt: Fmt) -> str:
    """Convenience: render a single table in one format."""
    return renderer_for(fmt).table(table)


def render_document(doc: Document, fmt: Fmt) -> str:
    """Convenience: render a sectioned document in one format."""
    return renderer_for(fmt).document(doc)
