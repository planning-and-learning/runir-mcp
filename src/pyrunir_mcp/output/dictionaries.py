"""Run-global alias dictionaries (interning).

Each distinct symbol/value is listed once and referenced everywhere by a short alias
`<prefix><index>` (`f`eatures, `r`ules, `a`ctions, `p` atoms, `m`emory, `v`ariables). See
docs/output/runir.ps.base.counterexamples.md#conventions.
"""

from __future__ import annotations

from typing import Hashable

from pyrunir_mcp.json_types import JsonValue
from pyrunir_mcp.tables import Table


class Dictionary:
    """Ordered get-or-assign registry: a value key maps to alias `<prefix><index>`."""

    def __init__(self, prefix: str, columns: list[str]) -> None:
        self._prefix = prefix
        self._columns = columns  # excluding the leading "id"
        self._alias_by_key: dict[Hashable, str] = {}
        self._keys: list[Hashable] = []
        self._rows: list[list[JsonValue]] = []

    def intern(self, key: Hashable, cells: list[JsonValue]) -> str:
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

    def table(self, name: str) -> Table | None:
        if not self._rows:
            return None
        return Table(name=name, columns=["id", *self._columns], rows=[list(row) for row in self._rows])


class Dictionaries:
    """The dictionaries shared by the policy and classifier families.

    `ext=True` gives module-program `rules` (`symbol|src|tgt`) and populates `memory`; base
    policy and classifier runs simply leave the unused dictionaries empty (omitted on render).
    """

    def __init__(self, *, ext: bool = False) -> None:
        self._ext = ext
        self.features = Dictionary("f", ["symbol"])
        self.rules = Dictionary("r", ["symbol", "src", "tgt"] if ext else ["symbol"])
        self.actions = Dictionary("a", ["action"])
        self.atoms = Dictionary("p", ["kind", "atom"])
        self.memories = Dictionary("m", ["module", "memory", "kind"])

    def feature(self, symbol: str) -> str:
        return self.features.intern(symbol, [symbol])

    def action(self, action: str) -> str:
        return self.actions.intern(action, [action])

    def atom(self, kind: str, atom: str) -> str:
        return self.atoms.intern((kind, atom), [kind, atom])

    def memory(self, module: str, memory: str, kind: str) -> str:
        return self.memories.intern((module, memory, kind), [module, memory, kind])

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
            "memory": self.memories,
        }
        return {name: table for name, dictionary in named.items() if (table := dictionary.table(name)) is not None}
