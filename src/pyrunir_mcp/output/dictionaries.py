"""Run-global alias dictionaries (interning).

Each distinct symbol/value is listed once and referenced everywhere by a short alias
`<prefix><index>` (`f`eatures, `r`ules, `a`ctions, `p` atoms, `M`odules, `m`emory, `v`ariables). See
the shared PSV/Markdown/JSON output conventions.
"""

from __future__ import annotations

from enum import StrEnum
from collections.abc import Sequence
from typing import Hashable

from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.tables import Table


class AtomKind(StrEnum):
    FLUENT = "fluent"
    DERIVED = "derived"
    STATIC = "static"


class Dictionary:
    """Ordered get-or-assign registry: a value key maps to alias `<prefix><index>`."""

    def __init__(self, prefix: str, columns: list[str]) -> None:
        self._prefix = prefix
        self._columns = columns  # excluding the leading "id"
        self._alias_by_key: dict[Hashable, str] = {}
        self._keys: list[Hashable] = []
        self._rows: list[list[JsonValue]] = []

    def intern(self, key: Hashable, cells: Sequence[JsonValue]) -> str:
        alias = self._alias_by_key.get(key)
        if alias is None:
            alias = f"{self._prefix}{len(self._rows)}"
            self._alias_by_key[key] = alias
            self._keys.append(key)
            self._rows.append([alias, *cells])
        return alias

    def alias_for(self, key: Hashable) -> str | None:
        """Return an already-interned alias without creating one."""
        return self._alias_by_key.get(key)

    def ordered_keys(self) -> list[Hashable]:
        return list(self._keys)

    def table(self, name: str, *, include_empty: bool = False) -> Table | None:
        if not self._rows and not include_empty:
            return None
        return Table(
            name=name, columns=["id", *self._columns], rows=[list(row) for row in self._rows]
        )


class Dictionaries:
    """The dictionaries shared by the policy and classifier families.

    `ext=True` gives module-program `rules` (`symbol|source|target`) and populates `modules`/`memory`; base
    policy and classifier runs simply leave the unused dictionaries empty (omitted on render).
    """

    def __init__(self, *, ext: bool = False) -> None:
        self._ext = ext
        self.features = Dictionary("f", ["symbol"])
        self.rules = Dictionary("r", ["symbol", "source", "target"] if ext else ["symbol"])
        self.actions = Dictionary("a", ["action"])
        self.atoms = Dictionary("p", ["kind", "atom"])
        self.modules = Dictionary("M", ["module"])
        self.memories = Dictionary("m", ["module", "memory"])

    def feature(self, symbol: str) -> str:
        return self.features.intern(symbol, [symbol])

    def action(self, action: str) -> str:
        return self.actions.intern(action, [action])

    def atom(self, kind: AtomKind, atom: str) -> str:
        return self.atoms.intern((kind, atom), [kind.value, atom])

    def module(self, module: str) -> str:
        return self.modules.intern(module, [module])

    def memory(self, module_alias: str, memory: str) -> str:
        """Intern a memory state, keyed by (module alias, name). Names are only unique within a
        module, so the module alias (`M…`, from `module()`) disambiguates collisions."""
        return self.memories.intern((module_alias, memory), [module_alias, memory])

    def rule(self, symbol: str, src: str | None = None, tgt: str | None = None) -> str:
        """Intern a rule, keyed by symbol. `src`/`tgt` are memory aliases for ext rules; ext
        rows always carry the three columns even if memory is unknown (so lazy interning of an
        unexpected rule symbol stays well-formed)."""
        cells = [symbol, src or "", tgt or ""] if self._ext else [symbol]
        return self.rules.intern(symbol, cells)

    def rule_alias(self, symbol: str) -> str | None:
        """Look up a rule alias by symbol without interning (rules are populated up front)."""
        return self.rules.alias_for(symbol)

    def feature_symbols(self) -> list[str]:
        """The interned feature symbols, in alias order (`f0`, `f1`, …)."""
        return [str(key) for key in self.features.ordered_keys()]

    def tables(self) -> dict[str, Table]:
        named = {
            "features": self.features,
            "rules": self.rules,
            "actions": self.actions,
            "atoms": self.atoms,
            "modules": self.modules,
            "memory": self.memories,
        }
        return {
            name: table
            for name, dictionary in named.items()
            if (table := dictionary.table(name)) is not None
        }
