import pytest

from regexlib import Regex, RegexSyntaxError, compile as regexlib_compile, findall, match, search

from .cases import UNAMBIGUOUS_CASES
from .helpers import re_whole_matches


def test_compile_and_match():
    r = regexlib_compile(r"\d+")
    m = r.match("123abc")
    assert m is not None
    assert m.group() == "123"
    assert m.span() == (0, 3)


def test_match_returns_none_on_failure():
    r = regexlib_compile(r"\d+")
    assert r.match("abc") is None


def test_fullmatch():
    r = regexlib_compile(r"\d+")
    assert r.fullmatch("12345") is not None
    assert r.fullmatch("12345x") is None


def test_search():
    r = regexlib_compile(r"\d+")
    m = r.search("abc 123 def")
    assert m.group() == "123"
    assert m.span() == (4, 7)


def test_findall_and_finditer_agree():
    r = regexlib_compile(r"\w+")
    text = "the quick brown fox"
    assert r.findall(text) == ["the", "quick", "brown", "fox"]
    assert [m.group() for m in r.finditer(text)] == r.findall(text)


def test_module_level_functions():
    assert match(r"\d+", "123abc").group() == "123"
    assert search(r"\d+", "abc123").group() == "123"
    assert findall(r"\d+", "a1 b22 c333") == ["1", "22", "333"]


def test_ignorecase_flag():
    r = regexlib_compile("hello", ignorecase=True)
    assert r.match("HELLO") is not None
    r_sensitive = regexlib_compile("hello", ignorecase=False)
    assert r_sensitive.match("HELLO") is None


def test_bad_pattern_raises_regex_syntax_error():
    with pytest.raises(RegexSyntaxError):
        regexlib_compile("(unclosed")


def test_unknown_engine_rejected():
    with pytest.raises(ValueError):
        Regex("abc", engine="dfa-turbo")


def test_match_object_repr_and_len():
    r = regexlib_compile(r"\d+")
    m = r.search("x42y")
    assert len(m) == 2
    assert "42" in repr(m)


@pytest.mark.parametrize("pattern,text", UNAMBIGUOUS_CASES)
def test_both_engines_agree_with_each_other_and_stdlib_re(pattern, text):
    nfa_result = regexlib_compile(pattern, engine="nfa").findall(text)
    backtrack_result = regexlib_compile(pattern, engine="backtrack").findall(text)
    expected = re_whole_matches(pattern, text)
    assert nfa_result == expected
    assert backtrack_result == expected
    assert nfa_result == backtrack_result


def test_regex_repr():
    r = regexlib_compile("abc")
    assert "abc" in repr(r)
    assert "nfa" in repr(r)
