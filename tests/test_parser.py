import pytest

from regexlib.ast_nodes import (
    AnyChar,
    Alternate,
    CharClass,
    Concat,
    Empty,
    Group,
    Literal,
    Optional,
    Plus,
    Star,
)
from regexlib.errors import RegexSyntaxError
from regexlib.parser import parse


def test_literal():
    assert parse("a") == Literal("a")


def test_concat():
    assert parse("ab") == Concat((Literal("a"), Literal("b")))


def test_anychar():
    assert parse(".") == AnyChar()


def test_star_plus_optional():
    assert parse("a*") == Star(Literal("a"))
    assert parse("a+") == Plus(Literal("a"))
    assert parse("a?") == Optional(Literal("a"))


def test_alternation():
    assert parse("a|b") == Alternate((Literal("a"), Literal("b")))
    assert parse("a|b|c") == Alternate((Literal("a"), Literal("b"), Literal("c")))


def test_group_wraps_child():
    assert parse("(a)") == Group(Literal("a"))


def test_group_controls_precedence():
    # Without grouping, "|" has lowest precedence: ab|cd == (ab)|(cd)
    assert parse("ab|cd") == Alternate((
        Concat((Literal("a"), Literal("b"))),
        Concat((Literal("c"), Literal("d"))),
    ))
    # With grouping, the quantifier binds to the whole group.
    assert parse("(ab)*") == Star(Group(Concat((Literal("a"), Literal("b")))))


def test_escaped_metacharacters_are_literal():
    for meta in ".*+?|()[]\\":
        assert parse("\\" + meta) == Literal(meta)


def test_simple_escapes():
    assert parse(r"\n") == Literal("\n")
    assert parse(r"\t") == Literal("\t")


def test_shorthand_classes():
    assert parse(r"\d") == CharClass((("0", "9"),), False)
    assert parse(r"\D") == CharClass((("0", "9"),), True)


def test_charclass_basic():
    node = parse("[abc]")
    assert node == CharClass((("a", "a"), ("b", "b"), ("c", "c")), False)


def test_charclass_range():
    node = parse("[a-z]")
    assert node == CharClass((("a", "z"),), False)


def test_charclass_negated():
    node = parse("[^abc]")
    assert node == CharClass((("a", "a"), ("b", "b"), ("c", "c")), True)


def test_charclass_leading_caret_and_bracket_are_literal_positions():
    # ']' immediately after '[' (or after '[^') is a literal ']', not the
    # closing bracket -- standard regex convention.
    node = parse("[]a]")
    assert node == CharClass((("]", "]"), ("a", "a")), False)
    node2 = parse("[^]a]")
    assert node2 == CharClass((("]", "]"), ("a", "a")), True)


def test_charclass_with_shorthand_inside():
    node = parse(r"[\d_]")
    assert node == CharClass((("0", "9"), ("_", "_")), False)


def test_empty_pattern():
    assert parse("") == Empty()


def test_empty_group():
    assert parse("()") == Group(Empty())


def test_bounded_repetition_exact():
    # a{3} == aaa
    assert parse("a{3}") == Concat((Literal("a"), Literal("a"), Literal("a")))


def test_bounded_repetition_range():
    # a{2,3} == aa a?
    assert parse("a{2,3}") == Concat((Literal("a"), Literal("a"), Optional(Literal("a"))))


def test_bounded_repetition_open_ended():
    # a{2,} == a a+
    assert parse("a{2,}") == Concat((Literal("a"), Plus(Literal("a"))))


def test_bounded_repetition_zero_min_unbounded():
    assert parse("a{0,}") == Star(Literal("a"))


def test_unrecognized_brace_is_literal():
    # Not a valid bound (non-digit) -- '{' and '}' are ordinary literals.
    assert parse("a{x}") == Concat((Literal("a"), Literal("{"), Literal("x"), Literal("}")))


def test_unmatched_paren_raises():
    with pytest.raises(RegexSyntaxError):
        parse("(abc")
    with pytest.raises(RegexSyntaxError):
        parse("abc)")


def test_nothing_to_repeat_raises():
    with pytest.raises(RegexSyntaxError):
        parse("*abc")
    with pytest.raises(RegexSyntaxError):
        parse("a|*b")


def test_double_quantifier_is_allowed_and_composes():
    # a** means Star(Star(a)) -- wasteful but not an error, same as most
    # regex engines (some reject it; we don't, to keep the parser simple).
    assert parse("a**") == Star(Star(Literal("a")))


def test_unterminated_charclass_raises():
    with pytest.raises(RegexSyntaxError):
        parse("[abc")


def test_empty_charclass_raises():
    with pytest.raises(RegexSyntaxError):
        parse("[]")


def test_trailing_backslash_raises():
    with pytest.raises(RegexSyntaxError):
        parse("a\\")


def test_bad_range_raises():
    with pytest.raises(RegexSyntaxError):
        parse("[z-a]")


def test_bad_bound_min_greater_than_max_raises():
    with pytest.raises(RegexSyntaxError):
        parse("a{4,2}")


def test_syntax_error_message_has_position():
    with pytest.raises(RegexSyntaxError) as exc_info:
        parse("ab)")
    assert exc_info.value.pos == 2
