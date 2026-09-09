"""Turn AST leaf nodes into character-matching predicates.

Shared by both engines (`nfa.py` and `backtrack.py`) so that "does this
character match this leaf node" has exactly one implementation.
"""

from __future__ import annotations

from typing import Callable

from .ast_nodes import AnyChar, CharClass, Literal, Node

Predicate = Callable[[str], bool]


def predicate_for(node: Node, ignorecase: bool = False) -> Predicate:
    """Build a predicate function for a single-character-consuming leaf node.

    Only ``Literal``, ``AnyChar`` and ``CharClass`` are valid here -- the
    caller (NFA builder / backtracker) is responsible for recursing into
    the structural node types (Concat, Alternate, Star, ...) itself.
    """
    if isinstance(node, Literal):
        return _literal_predicate(node.char, ignorecase)
    if isinstance(node, AnyChar):
        return _any_predicate()
    if isinstance(node, CharClass):
        return _charclass_predicate(node.ranges, node.negate, ignorecase)
    raise TypeError(f"predicate_for: not a leaf node: {node!r}")


def _literal_predicate(target: str, ignorecase: bool) -> Predicate:
    if ignorecase:
        target_folded = target.lower()

        def pred(c: str) -> bool:
            return c.lower() == target_folded

        return pred

    def pred(c: str) -> bool:
        return c == target

    return pred


def _any_predicate() -> Predicate:
    def pred(c: str) -> bool:
        return c != "\n"

    return pred


def _charclass_predicate(ranges, negate: bool, ignorecase: bool) -> Predicate:
    if ignorecase:
        expanded = []
        for lo, hi in ranges:
            expanded.append((lo, hi))
            expanded.append((lo.lower(), hi.lower()))
            expanded.append((lo.upper(), hi.upper()))
        ranges = tuple(expanded)

    def pred(c: str) -> bool:
        inside = any(lo <= c <= hi for lo, hi in ranges)
        return inside != negate

    return pred
