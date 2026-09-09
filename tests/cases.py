"""Shared (pattern, text) fixtures used across test modules.

``UNAMBIGUOUS_CASES`` are patterns where leftmost-longest and
leftmost-first matching agree on every match in ``text`` -- so they're
used to cross-check *both* engines against Python's own `re` module,
which is about as strong a correctness oracle as we can get for a
from-scratch implementation. ``AMBIGUOUS_CASES`` are kept separate and
exercised only in the tests that specifically document the semantic
difference between the two engines.
"""

# (pattern, text) -- both regexlib engines must produce results
# byte-for-byte identical to `re.findall`/`re.search` on these.
UNAMBIGUOUS_CASES = [
    (r"abc", "xxabcxx"),
    (r"abc", "no match here"),
    (r"a.c", "abc axc a\nc"),
    (r"a.c", ""),
    (r"colou?r", "color colour colouur"),
    (r"go+gle", "gogle google gooogle ggle"),
    (r"a*", "aaab"),
    (r"a*", ""),
    (r"[abc]+", "aabbccdd cabbage"),
    (r"[^abc]+", "aabbccdd cabbage"),
    (r"[a-z]+", "Hello World 123"),
    (r"[A-Za-z0-9_]+", "snake_case_123 and-not-this"),
    (r"[a-f0-9]{2}", "deadbeef CAFE"),
    (r"\d+", "room 42, aisle 7, year 2026"),
    (r"\D+", "room 42, aisle 7, year 2026"),
    (r"\w+", "hello_world-42 foo"),
    (r"\W+", "hello_world-42 foo!!"),
    (r"\s+", "a  b\tc\nd"),
    (r"\S+", "a  b\tc\nd"),
    (r"cat|dog|bird", "I have a cat, a dog, and a bird"),
    (r"(ab)+", "abababx ab"),
    (r"(foo|bar)baz", "foobaz barbaz bazbaz"),
    (r"colou?r|gr[ae]y", "color grey gray colour black"),
    (r"[0-9]{3}-[0-9]{4}", "call 555-1234 or 12-34"),
    (r"a{2,4}", "a aa aaa aaaa aaaaa"),
    (r"a{0,2}b", "b ab aab aaab"),
    (r"x{3,}", "x xx xxx xxxx"),
    (r"(https?://)?example\.com", "visit http://example.com or https://example.com or example.com"),
    (r"[\d]+\.[\d]+", "pi is 3.14159 and e is 2.71828"),
]

# Anchored-match (re.match semantics) cases: (pattern, text) pairs where
# a prefix match is expected to agree between engines and `re.match`.
ANCHORED_UNAMBIGUOUS_CASES = [
    (r"a+", "aaab"),
    (r"[A-Z][a-z]*", "Hello world"),
    (r"\d{3}", "123abc"),
    (r"foo", "foobar"),
    (r"foo", "barfoo"),
    (r"(a|ab)c", "ac"),  # unambiguous here: only "a" branch can lead to a full match
]

# Cases where leftmost-longest (NFA) and leftmost-first (backtrack, re)
# genuinely disagree -- documented explicitly rather than papered over.
AMBIGUOUS_CASES = [
    # re/backtrack: leftmost-first alternative "a" wins over "ab".
    # nfa: leftmost-LONGEST wins, i.e. "ab".
    (r"a|ab", "ab", "a", "ab"),
    (r"ab|a", "ab", "ab", "ab"),  # here both agree since first alt IS the longest
    (r"a?a", "a", "a", "a"),
]
