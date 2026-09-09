r"""Recursive-descent parser: regex pattern string -> AST.

Grammar (informal EBNF; `.` is any-char, concatenation is juxtaposition):

    alternation := concat ('|' concat)*
    concat      := repeat*
    repeat      := atom quantifier?
    quantifier  := '*' | '+' | '?' | '{' INT (',' INT?)? '}'
    atom        := literal | '.' | charclass | '(' alternation ')' | escape
    charclass   := '[' '^'? class_item+ ']'
    class_item  := class_char ('-' class_char)?
    class_char  := any char except ']' (unless first) | escape
    escape      := '\' (d|D|w|W|s|S|n|r|t|f|v|0|any other char, taken literally)

Metacharacters `. * + ? | ( ) [ ] \` must be escaped with `\` to match
literally. `{` and `}` are only special when they form a valid bound
quantifier immediately after an atom; otherwise they're literal
characters (this matches common grep/PCRE-lite behavior and keeps
`{` usable in plain text patterns without escaping).

Bounded repetition `{m}`, `{m,}`, `{m,n}` is desugared here into
Concat/Optional/Star/Plus combinations, so the AST consumed by the NFA
builder and the backtracking matcher never has to know about it.
"""

from __future__ import annotations

from typing import List, Optional as Opt, Tuple

from .ast_nodes import (
    AnyChar,
    Alternate,
    CharClass,
    Concat,
    Empty,
    Group,
    Literal,
    Node,
    Optional,
    Plus,
    Star,
)
from .errors import RegexSyntaxError

_METACHARS = set(".*+?|()[]\\")

DIGIT_RANGES: Tuple[Tuple[str, str], ...] = (("0", "9"),)
WORD_RANGES: Tuple[Tuple[str, str], ...] = (("a", "z"), ("A", "Z"), ("0", "9"), ("_", "_"))
SPACE_RANGES: Tuple[Tuple[str, str], ...] = (
    (" ", " "),
    ("\t", "\t"),
    ("\n", "\n"),
    ("\r", "\r"),
    ("\f", "\f"),
    ("\v", "\v"),
)

_SIMPLE_ESCAPES = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "f": "\f",
    "v": "\v",
    "0": "\0",
}

_SHORTHAND_CLASSES = {
    "d": (DIGIT_RANGES, False),
    "D": (DIGIT_RANGES, True),
    "w": (WORD_RANGES, False),
    "W": (WORD_RANGES, True),
    "s": (SPACE_RANGES, False),
    "S": (SPACE_RANGES, True),
}


class _ClassMarker:
    """Sentinel returned by ``_read_class_char`` for a `\\d`-style shorthand."""

    __slots__ = ("ranges", "negate")

    def __init__(self, ranges: Tuple[Tuple[str, str], ...], negate: bool):
        self.ranges = ranges
        self.negate = negate


class Parser:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.pos = 0
        self.n = len(pattern)

    # -- low-level cursor helpers -----------------------------------
    def _peek(self) -> Opt[str]:
        return self.pattern[self.pos] if self.pos < self.n else None

    def _peek_at(self, offset: int) -> Opt[str]:
        idx = self.pos + offset
        return self.pattern[idx] if idx < self.n else None

    def _advance(self) -> str:
        c = self.pattern[self.pos]
        self.pos += 1
        return c

    def _expect(self, ch: str) -> None:
        if self._peek() != ch:
            got = self._peek()
            self._error(f"expected {ch!r}, got {got!r}")
        self._advance()

    def _error(self, message: str, pos: Opt[int] = None) -> None:
        raise RegexSyntaxError(message, self.pattern, self.pos if pos is None else pos)

    # -- entry point ---------------------------------------------------
    def parse(self) -> Node:
        node = self._parse_alternation()
        if self.pos != self.n:
            self._error(f"unexpected {self._peek()!r}")
        return node

    # -- grammar rules ---------------------------------------------------
    def _parse_alternation(self) -> Node:
        branches: List[Node] = [self._parse_concat()]
        while self._peek() == "|":
            self._advance()
            branches.append(self._parse_concat())
        if len(branches) == 1:
            return branches[0]
        return Alternate(tuple(branches))

    def _parse_concat(self) -> Node:
        parts: List[Node] = []
        while self._peek() is not None and self._peek() not in "|)":
            parts.append(self._parse_repeat())
        if not parts:
            return Empty()
        if len(parts) == 1:
            return parts[0]
        return Concat(tuple(parts))

    def _parse_repeat(self) -> Node:
        start_pos = self.pos
        atom = self._parse_atom()
        while True:
            c = self._peek()
            if c == "*":
                self._advance()
                atom = Star(atom)
            elif c == "+":
                self._advance()
                atom = Plus(atom)
            elif c == "?":
                self._advance()
                atom = Optional(atom)
            elif c == "{":
                bound = self._try_parse_bound(atom, start_pos)
                if bound is None:
                    break
                atom = bound
            else:
                break
        return atom

    def _try_parse_bound(self, atom: Node, atom_start: int) -> Opt[Node]:
        """Try to parse a `{m}`/`{m,}`/`{m,n}` quantifier at the cursor.

        Returns the desugared node on success, or ``None`` (consuming
        nothing) if what follows `{` isn't a valid bound -- in that case
        `{` is treated as an ordinary literal by the caller's loop.
        """
        save = self.pos
        assert self._peek() == "{"
        self._advance()
        m_digits = self._read_digits()
        if m_digits == "":
            self.pos = save
            return None
        m = int(m_digits)
        n: Opt[int]
        if self._peek() == ",":
            self._advance()
            n_digits = self._read_digits()
            n = int(n_digits) if n_digits != "" else None
        else:
            n = m
        if self._peek() != "}":
            self.pos = save
            return None
        self._advance()
        if n is not None and n < m:
            self._error(f"bad repeat interval {{{m},{n}}}: min > max", atom_start)
        return self._desugar_bound(atom, m, n)

    def _read_digits(self) -> str:
        start = self.pos
        while self._peek() is not None and self._peek().isdigit():
            self._advance()
        return self.pattern[start:self.pos]

    @staticmethod
    def _desugar_bound(atom: Node, m: int, n: Opt[int]) -> Node:
        if n is None:
            if m == 0:
                return Star(atom)
            parts = [atom] * (m - 1) + [Plus(atom)]
            return parts[0] if len(parts) == 1 else Concat(tuple(parts))
        if m == 0 and n == 0:
            return Empty()
        required = [atom] * m
        optional = [Optional(atom)] * (n - m)
        parts = required + optional
        if not parts:
            return Empty()
        if len(parts) == 1:
            return parts[0]
        return Concat(tuple(parts))

    def _parse_atom(self) -> Node:
        c = self._peek()
        if c is None:
            self._error("unexpected end of pattern")
        if c == "(":
            self._advance()
            inner = self._parse_alternation()
            if self._peek() != ")":
                self._error("unbalanced parenthesis: expected ')'")
            self._advance()
            return Group(inner)
        if c == ")":
            self._error("unbalanced parenthesis: unexpected ')'")
        if c == ".":
            self._advance()
            return AnyChar()
        if c == "[":
            return self._parse_charclass()
        if c == "\\":
            return self._parse_escape()
        if c in "*+?":
            self._error(f"nothing to repeat: {c!r}")
        self._advance()
        return Literal(c)

    def _parse_escape(self) -> Node:
        self._advance()  # consume backslash
        c = self._peek()
        if c is None:
            self._error("trailing backslash")
        self._advance()
        if c in _SHORTHAND_CLASSES:
            ranges, negate = _SHORTHAND_CLASSES[c]
            return CharClass(ranges, negate)
        if c in _SIMPLE_ESCAPES:
            return Literal(_SIMPLE_ESCAPES[c])
        return Literal(c)

    def _parse_charclass(self) -> Node:
        self._expect("[")
        negate = False
        if self._peek() == "^":
            negate = True
            self._advance()
        items: List[Tuple[str, str]] = []
        first = True
        while True:
            c = self._peek()
            if c is None:
                self._error("unterminated character class")
            if c == "]" and not first:
                self._advance()
                break
            first = False
            lo = self._read_class_char()
            if isinstance(lo, _ClassMarker):
                items.extend(lo.ranges if not lo.negate else _negate_ranges(lo.ranges))
                continue
            if self._peek() == "-" and self._peek_at(1) is not None and self._peek_at(1) != "]":
                self._advance()  # consume '-'
                hi = self._read_class_char()
                if isinstance(hi, _ClassMarker):
                    self._error("invalid range endpoint (shorthand class)")
                if ord(hi) < ord(lo):
                    self._error(f"bad character range {lo}-{hi}")
                items.append((lo, hi))
            else:
                items.append((lo, lo))
        if not items:
            self._error("empty character class")
        return CharClass(tuple(items), negate)

    def _read_class_char(self):
        c = self._advance()
        if c != "\\":
            return c
        if self._peek() is None:
            self._error("trailing backslash in character class")
        e = self._advance()
        if e in _SHORTHAND_CLASSES:
            ranges, negate = _SHORTHAND_CLASSES[e]
            return _ClassMarker(ranges, negate)
        if e in _SIMPLE_ESCAPES:
            return _SIMPLE_ESCAPES[e]
        return e


def _negate_ranges(ranges: Tuple[Tuple[str, str], ...]) -> Tuple[Tuple[str, str], ...]:
    """Materialize the complement of ``ranges`` over the printable/ASCII
    range used by shorthand classes, as concrete (lo, hi) pairs.

    Only used for negated shorthand-inside-class (`[\\D]` etc.), which is
    rare; a straightforward full-codepoint complement keeps this simple
    and correct rather than fast.
    """
    covered = set()
    for lo, hi in ranges:
        for code in range(ord(lo), ord(hi) + 1):
            covered.add(code)
    out: List[Tuple[str, str]] = []
    start = None
    for code in range(0, 0x110000):
        if code not in covered:
            if start is None:
                start = code
        else:
            if start is not None:
                out.append((chr(start), chr(code - 1)))
                start = None
    if start is not None:
        out.append((chr(start), chr(0x10FFFF)))
    return tuple(out)


def parse(pattern: str) -> Node:
    return Parser(pattern).parse()
