import re
import time

import pytest

from regexlib.backtrack import StepLimitExceeded, finditer, fullmatch_at, match_at, search
from regexlib.parser import parse

from .cases import ANCHORED_UNAMBIGUOUS_CASES, UNAMBIGUOUS_CASES
from .helpers import re_whole_matches


def _bt_findall(pattern: str, text: str):
    ast = parse(pattern)
    return [text[s:e] for s, e in finditer(ast, text)]


@pytest.mark.parametrize("pattern,text", UNAMBIGUOUS_CASES)
def test_findall_matches_stdlib_re(pattern, text):
    assert _bt_findall(pattern, text) == re_whole_matches(pattern, text)


@pytest.mark.parametrize("pattern,text", ANCHORED_UNAMBIGUOUS_CASES)
def test_match_matches_stdlib_re(pattern, text):
    ast = parse(pattern)
    end = match_at(ast, text, 0)
    ref = re.match(pattern, text)
    if ref is None:
        assert end is None
    else:
        assert end == ref.end()


def test_leftmost_first_semantics():
    # Unlike the NFA engine, backtracking prefers the FIRST alternative
    # that leads to *any* success, even if a later one would match more.
    ast = parse(r"a|ab")
    assert match_at(ast, "ab", 0) == 1  # "a", not "ab"


def test_fullmatch():
    ast = parse(r"\d+")
    assert fullmatch_at(ast, "12345", 0) is True
    assert fullmatch_at(ast, "12345x", 0) is False


def test_search():
    ast = parse(r"\d+")
    assert search(ast, "abc 123 def") == (4, 7)
    assert search(ast, "no digits") is None


def test_empty_repetition_does_not_infinite_loop():
    # (a*)* on a string with no 'a's: the inner a* matches empty
    # immediately, and without the empty-match guard a naive
    # implementation would recurse forever trying to repeat "nothing"
    # infinitely. Must terminate promptly.
    ast = parse(r"(a*)*")
    start = time.monotonic()
    end = match_at(ast, "bbbb", 0)
    elapsed = time.monotonic() - start
    assert end == 0  # matches empty prefix
    assert elapsed < 1.0


def test_empty_repetition_with_plus_does_not_infinite_loop():
    ast = parse(r"(a*)+b")
    start = time.monotonic()
    end = match_at(ast, "bbb", 0)
    elapsed = time.monotonic() - start
    assert end == 1  # (a*)+ matches empty once, then 'b' matches
    assert elapsed < 1.0


def test_step_limit_exceeded_on_catastrophic_pattern():
    # (a+)+b against a run of a's with no trailing b is the textbook
    # catastrophic-backtracking case: exponentially many ways to split
    # the a-run among repetitions of (a+), all of which ultimately fail
    # because there's no 'b'. A tight step_limit should trip well before
    # the naive search finishes (which, uncapped, would take a very long
    # time for n this size).
    ast = parse(r"(a+)+b")
    text = "a" * 28  # no trailing 'b' -> guaranteed to exhaust all splits
    with pytest.raises(StepLimitExceeded):
        match_at(ast, text, 0, step_limit=200_000)


def test_step_limit_not_hit_on_reasonable_pattern():
    ast = parse(r"(a+)+b")
    text = "a" * 10 + "b"
    end = match_at(ast, text, 0, step_limit=200_000)
    assert end == 11
