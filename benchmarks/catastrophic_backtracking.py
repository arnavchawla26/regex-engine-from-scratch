#!/usr/bin/env python3
"""Demonstrate catastrophic backtracking, and that the NFA engine doesn't
have it.

Pattern: ``(a+)+b`` against a run of ``n`` a's with *no* trailing ``b``.
Every way of partitioning the a-run among the repetitions of ``(a+)``
has to be tried by naive backtracking before it can conclude there's no
match -- roughly ``O(2^n)`` of them. The NFA engine tracks all of those
partitions *simultaneously* as one set of active states, so it stays
``O(n)``.

Run it:

    python benchmarks/catastrophic_backtracking.py

Sample output (numbers vary by machine, but the shape doesn't):

    n=10  nfa:   0.05ms   backtrack:     0.32ms
    n=15  nfa:   0.07ms   backtrack:     6.71ms
    n=20  nfa:   0.09ms   backtrack:   198.40ms
    n=22  nfa:   0.10ms   backtrack:   792.14ms
    n=24  nfa:   0.11ms   backtrack:  3170.55ms  (or: step_limit exceeded)

The backtracking column roughly quadruples every +2 to n, while the NFA
column barely moves -- that's the exponential-vs-linear gap made
concrete, not just asserted.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from regexlib import backtrack, simulate  # noqa: E402
from regexlib.backtrack import StepLimitExceeded  # noqa: E402
from regexlib.nfa import build  # noqa: E402
from regexlib.parser import parse  # noqa: E402

PATTERN = r"(a+)+b"
STEP_LIMIT = 5_000_000


def time_nfa(ast, text: str) -> float:
    nfa = build(ast)
    start = time.perf_counter()
    simulate.match_at(nfa, text, 0)
    return (time.perf_counter() - start) * 1000


def time_backtrack(ast, text: str) -> str:
    start = time.perf_counter()
    try:
        backtrack.match_at(ast, text, 0, step_limit=STEP_LIMIT)
    except StepLimitExceeded:
        return f">{(time.perf_counter() - start) * 1000:.2f}ms (step_limit hit)"
    return f"{(time.perf_counter() - start) * 1000:.2f}ms"


def main() -> None:
    ast = parse(PATTERN)
    print(f"pattern: {PATTERN!r}   (a-run of length n, no trailing 'b' -> guaranteed failure)")
    print()
    for n in (10, 15, 18, 20, 22, 24, 26):
        text = "a" * n
        nfa_ms = time_nfa(ast, text)
        bt = time_backtrack(ast, text)
        print(f"n={n:<3d} nfa: {nfa_ms:8.3f}ms   backtrack: {bt}")


if __name__ == "__main__":
    main()
