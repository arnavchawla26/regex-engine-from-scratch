"""High-level, `re`-flavored API on top of the two matching engines.

``compile()`` returns a :class:`Regex` bound to one engine:

* ``engine="nfa"`` (the default) -- Thompson NFA simulation. Always
  linear time in ``len(text)``, immune to catastrophic backtracking.
  Uses leftmost-*longest* match semantics.
* ``engine="backtrack"`` -- naive AST backtracking. Familiar
  leftmost-*first*/greedy semantics (matches Python's `re` on
  unambiguous patterns), but can be exponential on pathological
  patterns. Mainly here for comparison/benchmarking -- see
  `benchmarks/catastrophic_backtracking.py`.

Module-level ``match``/``search``/``findall``/``finditer`` mirror the
`re` module's free functions and always use the NFA engine, which is
the safe default for untrusted patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Optional

from . import backtrack, simulate
from .ast_nodes import Node
from .nfa import NFA, build as build_nfa
from .parser import parse as parse_pattern

__all__ = [
    "Match",
    "Regex",
    "compile",
    "match",
    "fullmatch",
    "search",
    "findall",
    "finditer",
]


@dataclass(frozen=True)
class Match:
    """A minimal stand-in for `re.Match` -- just span + matched text."""

    string: str
    start: int
    end: int

    def group(self) -> str:
        return self.string[self.start : self.end]

    def span(self):
        return (self.start, self.end)

    def __len__(self) -> int:
        return self.end - self.start

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Match(span=({self.start}, {self.end}), text={self.group()!r})"


class Regex:
    def __init__(self, pattern: str, ignorecase: bool = False, engine: str = "nfa"):
        if engine not in ("nfa", "backtrack"):
            raise ValueError(f"unknown engine {engine!r}: expected 'nfa' or 'backtrack'")
        self.pattern = pattern
        self.ignorecase = ignorecase
        self.engine = engine
        self.ast: Node = parse_pattern(pattern)
        self._nfa: Optional[NFA] = build_nfa(self.ast, ignorecase) if engine == "nfa" else None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Regex({self.pattern!r}, engine={self.engine!r})"

    # -- matching -----------------------------------------------------
    def match(self, text: str, pos: int = 0) -> Optional[Match]:
        """Anchored match at ``pos`` (like `re.match`, generalized to a
        starting offset). Returns the match if the pattern matches a
        prefix of ``text[pos:]``."""
        end = self._match_at(text, pos)
        if end is None:
            return None
        return Match(text, pos, end)

    def fullmatch(self, text: str, pos: int = 0) -> Optional[Match]:
        """Anchored match that must consume all of ``text[pos:]``."""
        if self.engine == "nfa":
            ok = simulate.fullmatch_at(self._nfa, text, pos)
            end = len(text) if ok else None
        else:
            ok = backtrack.fullmatch_at(self.ast, text, pos, ignorecase=self.ignorecase)
            end = len(text) if ok else None
        if end is None:
            return None
        return Match(text, pos, end)

    def search(self, text: str, pos: int = 0) -> Optional[Match]:
        """First match anywhere in ``text[pos:]`` (like `re.search`)."""
        if self.engine == "nfa":
            found = simulate.search(self._nfa, text, pos)
        else:
            found = backtrack.search(self.ast, text, pos, ignorecase=self.ignorecase)
        if found is None:
            return None
        s, e = found
        return Match(text, s, e)

    def finditer(self, text: str) -> Iterator[Match]:
        if self.engine == "nfa":
            for s, e in simulate.finditer(self._nfa, text):
                yield Match(text, s, e)
        else:
            for s, e in backtrack.finditer(self.ast, text, ignorecase=self.ignorecase):
                yield Match(text, s, e)

    def findall(self, text: str) -> List[str]:
        return [m.group() for m in self.finditer(text)]

    def _match_at(self, text: str, pos: int) -> Optional[int]:
        if self.engine == "nfa":
            return simulate.match_at(self._nfa, text, pos)
        return backtrack.match_at(self.ast, text, pos, ignorecase=self.ignorecase)


# -- module-level convenience functions (mirror `re`, always NFA engine) --


def compile(pattern: str, ignorecase: bool = False, engine: str = "nfa") -> Regex:
    return Regex(pattern, ignorecase=ignorecase, engine=engine)


def match(pattern: str, text: str, ignorecase: bool = False) -> Optional[Match]:
    return compile(pattern, ignorecase=ignorecase).match(text)


def fullmatch(pattern: str, text: str, ignorecase: bool = False) -> Optional[Match]:
    return compile(pattern, ignorecase=ignorecase).fullmatch(text)


def search(pattern: str, text: str, ignorecase: bool = False) -> Optional[Match]:
    return compile(pattern, ignorecase=ignorecase).search(text)


def findall(pattern: str, text: str, ignorecase: bool = False) -> List[str]:
    return compile(pattern, ignorecase=ignorecase).findall(text)


def finditer(pattern: str, text: str, ignorecase: bool = False) -> Iterator[Match]:
    return compile(pattern, ignorecase=ignorecase).finditer(text)
