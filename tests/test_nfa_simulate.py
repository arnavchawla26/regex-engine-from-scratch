import re

import pytest

from regexlib.nfa import build, count_states
from regexlib.parser import parse
from regexlib.simulate import finditer, match_at, search

from .cases import AMBIGUOUS_CASES, ANCHORED_UNAMBIGUOUS_CASES, UNAMBIGUOUS_CASES
from .helpers import re_whole_matches


def _nfa_findall(pattern: str, text: str):
    nfa = build(parse(pattern))
    return [text[s:e] for s, e in finditer(nfa, text)]


@pytest.mark.parametrize("pattern,text", UNAMBIGUOUS_CASES)
def test_findall_matches_stdlib_re(pattern, text):
    assert _nfa_findall(pattern, text) == re_whole_matches(pattern, text)


@pytest.mark.parametrize("pattern,text", ANCHORED_UNAMBIGUOUS_CASES)
def test_match_matches_stdlib_re(pattern, text):
    nfa = build(parse(pattern))
    end = match_at(nfa, text, 0)
    ref = re.match(pattern, text)
    if ref is None:
        assert end is None
    else:
        assert end == ref.end()


def test_search_finds_leftmost_start():
    nfa = build(parse(r"\d+"))
    result = search(nfa, "abc 123 def 456")
    assert result == (4, 7)
    assert "abc 123 def 456"[4:7] == "123"


def test_search_no_match_returns_none():
    nfa = build(parse(r"\d+"))
    assert search(nfa, "no digits here") is None


def test_match_at_requires_prefix_at_exact_position():
    nfa = build(parse(r"\d+"))
    # Anchored at 0, "abc123" doesn't start with a digit.
    assert match_at(nfa, "abc123", 0) is None
    # But anchored at 3, it does.
    assert match_at(nfa, "abc123", 3) == 6


def test_star_matches_empty_string():
    nfa = build(parse(r"a*"))
    assert match_at(nfa, "", 0) == 0
    assert match_at(nfa, "bbb", 0) == 0  # zero a's, still a valid (empty) match


def test_empty_pattern_matches_everywhere():
    nfa = build(parse(r""))
    assert match_at(nfa, "anything", 0) == 0


@pytest.mark.parametrize("pattern,text,leftmost_first,leftmost_longest", AMBIGUOUS_CASES)
def test_leftmost_longest_vs_leftmost_first(pattern, text, leftmost_first, leftmost_longest):
    """The NFA engine is leftmost-LONGEST; Python's re (and our backtracker)
    is leftmost-FIRST. These are genuinely different, standard matching
    disciplines -- this test documents exactly where they diverge rather
    than treating it as a bug in either engine."""
    nfa = build(parse(pattern))
    end = match_at(nfa, text, 0)
    assert text[0:end] == leftmost_longest

    ref = re.match(pattern, text)
    assert ref is not None and ref.group() == leftmost_first


def test_ignorecase():
    nfa = build(parse("hello"), ignorecase=True)
    assert match_at(nfa, "HELLO", 0) == 5
    assert match_at(nfa, "HeLLo", 0) == 5
    nfa_sensitive = build(parse("hello"), ignorecase=False)
    assert match_at(nfa_sensitive, "HELLO", 0) is None


def test_nfa_state_count_is_linear_in_pattern_length():
    # A concatenation of k literals should produce O(k) states, not
    # something blown up by the recursive construction. This is the
    # property that makes {m,n} desugaring (which duplicates subtrees)
    # safe: it still only multiplies state count by a constant factor
    # per repeated atom, not exponentially.
    small = count_states(build(parse("a" * 5)))
    big = count_states(build(parse("a" * 50)))
    # Expect roughly linear growth (allow generous slack for per-literal
    # fragment overhead), definitely not something like 10x -> 100x+.
    ratio = big / small
    assert ratio < 15, f"state count grew {ratio}x for a 10x longer pattern"


def test_nested_quantifiers_stay_polynomial_sized():
    # (a{3}){3} desugars to 9 literal atoms -- still small and fast to
    # build, unlike naive backtracking's behavior on similar patterns.
    nfa = build(parse("(a{3}){3}"))
    assert match_at(nfa, "aaaaaaaaa", 0) == 9
    assert count_states(nfa) < 50
