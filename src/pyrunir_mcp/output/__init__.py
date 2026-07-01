"""Render run artifacts (dictionaries + witnesses) to the PSV/Markdown/JSON output format.

See docs/tables/*.md and the tool-specific docs/*.md pages for the on-disk format. This package builds the logical `Table`/
`Document` artifacts from the verbose witness dicts the services already produce, interning
long/recurring symbols into run-global dictionaries, and writes them via `tables.py`.
"""
