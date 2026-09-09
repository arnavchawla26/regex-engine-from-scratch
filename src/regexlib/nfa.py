"""Thompson's construction: AST -> NFA.

Follows the classic recursive construction (see Ken Thompson, "Regular
Expression Search Algorithm", 1968; also Russ Cox's "Regular Expression
Matching Can Be Simple And Fast"). Each AST node is compiled into a
*fragment*: a `(start_state, end_state)` pair where `end_state` has no
outgoing edges yet. Fragments are stitched together by adding epsilon
edges from one fragment's end into the next fragment's start, which is
why the recursive builder never needs to mutate more than the two
states it was just handed.

States have at most two outgoing edges. An edge is either:
  * an epsilon edge (`predicate is None`) -- always followable "for free"
  * a consuming edge (`predicate` is a `Callable[[str], bool]`) -- only
    followable by consuming one input character that satisfies it.

This keeps the automaton an NFA in the textbook sense (as opposed to
building a DFA directly), which is what lets `{m,n}` and nested
`(a|b)*`-style patterns compile in linear time and linear size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .ast_nodes import (
    AnyChar,
    Alternate,
    CharClass,
    Concat,
    Empty,
    Group,
    Literal,
    Node,
    Optional as OptionalNode,
    Plus,
    Star,
)
from .predicates import Predicate, predicate_for


@dataclass
class Edge:
    predicate: Optional[Predicate]  # None => epsilon
    target: "State"


class State:
    __slots__ = ("id", "edges")
    _counter = 0

    def __init__(self):
        State._counter += 1
        self.id = State._counter
        self.edges: List[Edge] = []

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"State(#{self.id})"


Fragment = Tuple[State, State]


@dataclass
class NFA:
    start: State
    accept: State


def build(node: Node, ignorecase: bool = False) -> NFA:
    """Compile an AST into a complete NFA with a single accept state."""
    start, end = _build_fragment(node, ignorecase)
    return NFA(start=start, accept=end)


def _build_fragment(node: Node, ignorecase: bool) -> Fragment:
    if isinstance(node, (Literal, AnyChar, CharClass)):
        return _frag_leaf(node, ignorecase)
    if isinstance(node, Empty):
        return _frag_empty()
    if isinstance(node, Concat):
        return _frag_concat(node, ignorecase)
    if isinstance(node, Alternate):
        return _frag_alternate(node, ignorecase)
    if isinstance(node, Star):
        return _frag_star(node, ignorecase)
    if isinstance(node, Plus):
        return _frag_plus(node, ignorecase)
    if isinstance(node, OptionalNode):
        return _frag_optional(node, ignorecase)
    if isinstance(node, Group):
        return _build_fragment(node.child, ignorecase)
    raise TypeError(f"nfa.build: unhandled node type {node!r}")


def _frag_leaf(node: Node, ignorecase: bool) -> Fragment:
    pred = predicate_for(node, ignorecase)
    start = State()
    end = State()
    start.edges.append(Edge(pred, end))
    return start, end


def _frag_empty() -> Fragment:
    start = State()
    end = State()
    start.edges.append(Edge(None, end))
    return start, end


def _frag_concat(node: Concat, ignorecase: bool) -> Fragment:
    fragments = [_build_fragment(p, ignorecase) for p in node.parts]
    start = fragments[0][0]
    prev_end = fragments[0][1]
    for s, e in fragments[1:]:
        prev_end.edges.append(Edge(None, s))
        prev_end = e
    return start, prev_end


def _frag_alternate(node: Alternate, ignorecase: bool) -> Fragment:
    start = State()
    end = State()
    for branch in node.branches:
        bs, be = _build_fragment(branch, ignorecase)
        start.edges.append(Edge(None, bs))
        be.edges.append(Edge(None, end))
    return start, end


def _frag_star(node: Star, ignorecase: bool) -> Fragment:
    s, e = _build_fragment(node.child, ignorecase)
    start = State()
    end = State()
    start.edges.append(Edge(None, s))
    start.edges.append(Edge(None, end))
    e.edges.append(Edge(None, s))
    e.edges.append(Edge(None, end))
    return start, end


def _frag_plus(node: Plus, ignorecase: bool) -> Fragment:
    s, e = _build_fragment(node.child, ignorecase)
    end = State()
    e.edges.append(Edge(None, s))
    e.edges.append(Edge(None, end))
    return s, end


def _frag_optional(node: OptionalNode, ignorecase: bool) -> Fragment:
    s, e = _build_fragment(node.child, ignorecase)
    start = State()
    end = State()
    start.edges.append(Edge(None, s))
    start.edges.append(Edge(None, end))
    e.edges.append(Edge(None, end))
    return start, end


def count_states(nfa: NFA) -> int:
    """Count reachable states -- used by tests/benchmarks to show that
    NFA size grows linearly with pattern length even for nested repeats."""
    seen = set()
    stack = [nfa.start]
    while stack:
        s = stack.pop()
        if s.id in seen:
            continue
        seen.add(s.id)
        for edge in s.edges:
            stack.append(edge.target)
    return len(seen)
