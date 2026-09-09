"""AST node types produced by the parser and consumed by both engines.

All nodes are frozen dataclasses (immutable, hashable-by-identity is not
needed since we never mutate them). {m,n} repetition is desugared by the
parser into Concat/Optional/Star combinations, so downstream code (the
NFA builder and the backtracking matcher) only ever has to handle the
node types defined here -- there is no separate "Repeat" node.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


class Node:
    """Base class for all AST nodes."""


@dataclass(frozen=True)
class Literal(Node):
    """Matches exactly one character (case-sensitivity applied by caller)."""

    char: str


@dataclass(frozen=True)
class AnyChar(Node):
    """Matches any single character (`.`)."""


@dataclass(frozen=True)
class CharClass(Node):
    """A `[...]` character class.

    ``ranges`` is a tuple of ``(lo, hi)`` inclusive character-code pairs
    (a single character is represented as ``(c, c)``). ``negate`` flips
    the match (`[^...]`).
    """

    ranges: Tuple[Tuple[str, str], ...]
    negate: bool = False


@dataclass(frozen=True)
class Concat(Node):
    """Sequence of nodes, matched one after another."""

    parts: Tuple[Node, ...]


@dataclass(frozen=True)
class Alternate(Node):
    """`a|b|c` -- matches if any branch matches."""

    branches: Tuple[Node, ...]


@dataclass(frozen=True)
class Star(Node):
    """`x*` -- zero or more, greedy."""

    child: Node


@dataclass(frozen=True)
class Plus(Node):
    """`x+` -- one or more, greedy."""

    child: Node


@dataclass(frozen=True)
class Optional(Node):
    """`x?` -- zero or one, greedy."""

    child: Node


@dataclass(frozen=True)
class Group(Node):
    """`(...)` -- a parenthesized subexpression.

    v1 only uses groups for precedence/grouping during parsing; the
    engines treat ``Group`` as a transparent wrapper around ``child``.
    ``index`` is reserved for a future capture-group extension and is
    always ``None`` for now.
    """

    child: Node
    index: int | None = None


@dataclass(frozen=True)
class Empty(Node):
    """Matches the empty string. Used for empty alternation branches/patterns."""
