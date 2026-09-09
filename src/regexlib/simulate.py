"""Simulate a Thompson NFA over input text without backtracking.

This is the classic "set of active states" simulation: at every input
position we track *every* NFA state reachable via epsilon transitions
from the states active a moment ago, then advance all of them at once by
one consumed character. Because we never abandon a path to try another
later (there's nothing to backtrack *into* -- all paths are explored in
lockstep), matching a string of length ``n`` against a pattern that
compiles to ``m`` states costs ``O(n * m)`` time, full stop. There is no
input on which this blows up exponentially, unlike naive backtracking
(see `backtrack.py` and `benchmarks/catastrophic_backtracking.py`).

Match semantics: because multiple divergent paths (e.g. both branches
of a `*`) are tracked simultaneously, an anchored match reports the
*longest* prefix for which some path reaches the accept state --
"leftmost-longest" matching. This differs from the "leftmost-first"
(a.k.a. Perl/PCRE) semantics used by `backtrack.py` and Python's `re`,
which always prefers whichever alternative or greedy-branch was written
first, even if a later option would match more text. `a|ab` against
`"ab"` is the textbook example where the two disagree -- see
`tests/test_nfa_simulate.py::test_leftmost_longest_vs_leftmost_first`.
"""

from __future__ import annotations

from typing import FrozenSet, Iterator, List, Optional, Tuple

from .nfa import NFA, State


def _epsilon_closure(states: List[State]) -> FrozenSet[int]:
    """Return the set of state ids reachable from ``states`` via epsilon
    edges only, including the states themselves. We also need the State
    objects, not just ids, so this returns an id->State dict."""
    stack = list(states)
    seen = {}
    for s in states:
        seen[s.id] = s
    while stack:
        s = stack.pop()
        for edge in s.edges:
            if edge.predicate is None and edge.target.id not in seen:
                seen[edge.target.id] = edge.target
                stack.append(edge.target)
    return seen


def match_at(nfa: NFA, text: str, start: int) -> Optional[int]:
    """Try to match ``nfa`` anchored at ``text[start:]``.

    Returns the end index of the longest match (so ``text[start:end]``
    is the matched substring), or ``None`` if no match starts at
    ``start`` at all. An end index equal to ``start`` means an empty
    match was found.
    """
    current = _epsilon_closure([nfa.start])
    best_end: Optional[int] = start if nfa.accept.id in current else None
    pos = start
    n = len(text)
    while pos < n and current:
        ch = text[pos]
        nxt_states = []
        for s in current.values():
            for edge in s.edges:
                if edge.predicate is not None and edge.predicate(ch):
                    nxt_states.append(edge.target)
        pos += 1
        if not nxt_states:
            current = {}
            break
        current = _epsilon_closure(nxt_states)
        if nfa.accept.id in current:
            best_end = pos
    return best_end


def fullmatch_at(nfa: NFA, text: str, start: int) -> bool:
    """True if the *entire* remainder ``text[start:]`` is matched."""
    end = match_at(nfa, text, start)
    return end == len(text)


def search(nfa: NFA, text: str, start: int = 0) -> Optional[Tuple[int, int]]:
    """Find the first (leftmost) match anywhere in ``text[start:]``.

    Among matches starting at the same (leftmost) position, the longest
    one wins (see module docstring). Returns ``(match_start, match_end)``
    or ``None``.
    """
    for pos in range(start, len(text) + 1):
        end = match_at(nfa, text, pos)
        if end is not None:
            return pos, end
    return None


def finditer(nfa: NFA, text: str) -> Iterator[Tuple[int, int]]:
    """Yield all non-overlapping matches left to right.

    After an empty match, the scan advances by one character to avoid
    looping forever, matching the convention used by Python's `re`.
    """
    pos = 0
    n = len(text)
    while pos <= n:
        found = search(nfa, text, pos)
        if found is None:
            return
        s, e = found
        yield s, e
        pos = e + 1 if e == s else e
