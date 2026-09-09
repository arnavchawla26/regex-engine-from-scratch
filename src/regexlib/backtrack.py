"""A naive recursive-descent backtracking matcher, operating directly on
the AST (no NFA involved at all).

This exists for two reasons: (1) as a second, independently-written
implementation to cross-check the NFA engine's results against in
tests, and (2) to make the classic "catastrophic backtracking" failure
mode reproducible and benchmarkable (see `benchmarks/`). Patterns like
``(a+)+b`` matched against a long run of ``a`` with no trailing ``b``
force this matcher to explore an exponential number of ways to
partition the string among the repetitions before giving up -- exactly
the behavior `simulate.py`'s NFA engine is immune to.

Semantics: greedy, leftmost-first (try the first alternative / "one
more repetition" before falling back), same convention as Perl/PCRE and
Python's `re` -- deliberately different from the NFA engine's
leftmost-longest semantics (see `simulate.py`'s module docstring).
"""

from __future__ import annotations

from typing import Callable, Optional

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
from .predicates import predicate_for

Continuation = Callable[[int], Optional[int]]


class StepLimitExceeded(RuntimeError):
    """Raised when a match exceeds an explicit ``step_limit``.

    Used by the benchmark/demo code to show catastrophic backtracking
    blowing past a reasonable budget without actually hanging.
    """


class _Matcher:
    def __init__(self, text: str, ignorecase: bool, step_limit: Optional[int]):
        self.text = text
        self.n = len(text)
        self.ignorecase = ignorecase
        self.step_limit = step_limit
        self.steps = 0

    def _tick(self) -> None:
        if self.step_limit is not None:
            self.steps += 1
            if self.steps > self.step_limit:
                raise StepLimitExceeded(
                    f"exceeded step_limit={self.step_limit} while backtracking"
                )

    def m(self, node: Node, pos: int, cont: Continuation) -> Optional[int]:
        self._tick()
        if isinstance(node, (Literal, AnyChar, CharClass)):
            if pos >= self.n:
                return None
            pred = predicate_for(node, self.ignorecase)
            if pred(self.text[pos]):
                return cont(pos + 1)
            return None
        if isinstance(node, Empty):
            return cont(pos)
        if isinstance(node, Group):
            return self.m(node.child, pos, cont)
        if isinstance(node, Concat):
            return self._match_concat(node.parts, 0, pos, cont)
        if isinstance(node, Alternate):
            for branch in node.branches:
                result = self.m(branch, pos, cont)
                if result is not None:
                    return result
            return None
        if isinstance(node, Star):
            return self._match_repeat(node.child, pos, cont, minimum=0)
        if isinstance(node, Plus):
            return self._match_repeat(node.child, pos, cont, minimum=1)
        if isinstance(node, OptionalNode):
            result = self.m(node.child, pos, cont)  # greedy: try "present" first
            if result is not None:
                return result
            return cont(pos)
        raise TypeError(f"backtrack matcher: unhandled node type {node!r}")

    def _match_concat(self, parts, index: int, pos: int, cont: Continuation) -> Optional[int]:
        if index == len(parts):
            return cont(pos)
        return self.m(parts[index], pos, lambda p: self._match_concat(parts, index + 1, p, cont))

    def _match_repeat(self, child: Node, pos: int, cont: Continuation, minimum: int) -> Optional[int]:
        def rec(p: int, count: int) -> Optional[int]:
            def after_one_more(p2: int) -> Optional[int]:
                if p2 == p:
                    # The repetition matched the empty string. Repeating it
                    # again can only ever match empty again -- recursing
                    # would loop forever, so treat this as the final
                    # repetition and stop (matches real engines' behavior
                    # on e.g. `(a*)*`).
                    if count + 1 >= minimum:
                        return cont(p2)
                    return None
                return rec(p2, count + 1)

            result = self.m(child, p, after_one_more)
            if result is not None:
                return result
            if count >= minimum:
                return cont(p)
            return None

        return rec(pos, 0)


def match_at(
    node: Node,
    text: str,
    start: int,
    ignorecase: bool = False,
    step_limit: Optional[int] = None,
) -> Optional[int]:
    """Anchored match at ``start``; returns end index of the first
    (leftmost-first, greedy) match, or ``None``."""
    matcher = _Matcher(text, ignorecase, step_limit)
    return matcher.m(node, start, lambda p: p)


def fullmatch_at(
    node: Node,
    text: str,
    start: int,
    ignorecase: bool = False,
    step_limit: Optional[int] = None,
) -> bool:
    matcher = _Matcher(text, ignorecase, step_limit)
    end = matcher.m(node, start, lambda p: p if p == len(text) else None)
    return end is not None


def search(
    node: Node,
    text: str,
    start: int = 0,
    ignorecase: bool = False,
    step_limit: Optional[int] = None,
):
    for pos in range(start, len(text) + 1):
        end = match_at(node, text, pos, ignorecase=ignorecase, step_limit=step_limit)
        if end is not None:
            return pos, end
    return None


def finditer(node: Node, text: str, ignorecase: bool = False):
    pos = 0
    n = len(text)
    while pos <= n:
        found = search(node, text, pos, ignorecase=ignorecase)
        if found is None:
            return
        s, e = found
        yield s, e
        pos = e + 1 if e == s else e
