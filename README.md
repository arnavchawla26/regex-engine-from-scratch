# regex-engine-from-scratch

A regex engine built from scratch, in pure Python, with no dependency on
the `re` module (or any other regex library) anywhere in the matching
path. It exists to answer, concretely rather than just in the abstract,
the question "why don't regex engines all backtrack, and what do they
do instead?"

It ships **two** independent matching engines behind the same API so you
can watch them disagree on both correctness-adjacent semantics and
performance:

* **`nfa`** (default) -- parses the pattern into an AST, compiles the
  AST into an NFA via [Thompson's construction][thompson], then
  simulates the NFA by tracking the *set* of all currently-active states
  at once (no backtracking, because there's nothing to backtrack into --
  every path is already being explored in lockstep). Matching is
  `O(n * m)` for input length `n` and compiled pattern size `m`,
  always, on every input.
* **`backtrack`** -- a textbook recursive backtracking matcher that
  walks the AST directly, trying alternatives and repetitions
  depth-first with a continuation-passing style. Familiar
  Perl/PCRE-style semantics, but exponential-time on adversarial
  patterns like `(a+)+b`.

[thompson]: https://en.wikipedia.org/wiki/Thompson%27s_construction

## Why two engines instead of one "correct" one

They're not just two implementations of the same thing -- they encode
genuinely different matching disciplines:

| | `nfa` | `backtrack` |
|---|---|---|
| Ambiguous match, e.g. `a\|ab` vs `"ab"` | **leftmost-longest** (`"ab"`) | **leftmost-first** (`"a"`, same as Perl/`re`) |
| Worst-case time | `O(n·m)`, always | can be exponential (`(a+)+b` style patterns) |
| Captures / backreferences | not supported (see Roadmap) | not supported (see Roadmap) |

Neither is "more correct" -- POSIX `grep -E` uses leftmost-longest,
while Perl, PCRE, Python's `re`, and most modern engines use
leftmost-first. `tests/test_nfa_simulate.py::test_leftmost_longest_vs_leftmost_first`
demonstrates the divergence directly instead of asserting one engine is
buggy for disagreeing with the other.

The performance gap is demonstrated, not just asserted, by
[`benchmarks/catastrophic_backtracking.py`](benchmarks/catastrophic_backtracking.py):

```
pattern: '(a+)+b'   (a-run of length n, no trailing 'b' -> guaranteed failure)

n=10  nfa:    0.035ms   backtrack: 4.92ms
n=15  nfa:    0.041ms   backtrack: 339.93ms
n=18  nfa:    0.052ms   backtrack: 1711.06ms
n=20  nfa:    0.061ms   backtrack: >5360.89ms (step_limit hit)
```

The `nfa` column barely moves; the `backtrack` column roughly
quadruples every two characters of input, and the demo has to give up
past `n=20` with a step-count budget rather than actually wait for it
(it would take a very long time).

## Pattern syntax

A deliberately small but real subset of common regex syntax:

| Syntax | Meaning |
|---|---|
| `a`, `b`, ... | literal characters |
| `.` | any character except newline |
| `a*`, `a+`, `a?` | zero-or-more / one-or-more / zero-or-one, greedy |
| `a{m}`, `a{m,}`, `a{m,n}` | bounded repetition (desugared at parse time into the above) |
| `a\|b` | alternation |
| `(...)` | grouping (precedence only -- no capturing yet, see Roadmap) |
| `[abc]`, `[a-z]`, `[^abc]` | character classes, ranges, negation |
| `\d \D \w \W \s \S` | digit / non-digit / word / non-word / whitespace / non-whitespace |
| `\n \t \r \f \v \0` | the usual control-character escapes |
| `\.`, `\*`, `\\`, ... | escape a metacharacter to match it literally |

`{` and `}` are only treated as a quantifier when they form a valid
bound (`{2}`, `{2,}`, `{2,5}`) immediately after an atom; otherwise
they're ordinary literal characters, so patterns like `a{x}` (not a
valid bound) don't need escaping.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Use it as a library

```python
import regexlib

r = regexlib.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
r.search("contact: dev@example.com please").group()   # 'dev@example.com'

regexlib.findall(r"\d+", "room 4, aisle 12")           # ['4', '12']

# pick the backtracking engine explicitly (e.g. for a benchmark/demo)
slow = regexlib.compile(r"(a+)+b", engine="backtrack")
```

`Regex` objects expose `.match(text, pos=0)` (anchored prefix match),
`.fullmatch(text, pos=0)`, `.search(text, pos=0)`, `.finditer(text)` and
`.findall(text)` -- a small, `re`-flavored subset. Match results are
plain `Match(string, start, end)` objects with `.group()`, `.span()`
and `len()`.

## Use the CLI (`regrep`)

A small `grep`-like tool over the same engine:

```bash
$ regrep '\d+' app.log                 # print matching lines
$ regrep -i 'error' app.log            # case-insensitive
$ regrep -v '\d+' app.log              # invert: print non-matching lines
$ regrep -c '\d+' app.log              # count matching lines
$ regrep -n '\d+' app.log              # prefix with line numbers
$ regrep -o '\d+' app.log              # print only the matched text
$ cat app.log | regrep '\d+'           # reads stdin when no files given
$ regrep --engine backtrack '\d+' app.log  # use the backtracking engine
```

Exit status follows `grep`'s convention: `0` if something matched, `1`
if nothing did, `2` on a bad pattern or unreadable file.

## Project layout

```
src/regexlib/
  ast_nodes.py    AST node types (Literal, CharClass, Concat, Alternate, Star, Plus, Optional, Group, Empty)
  parser.py       recursive-descent parser: pattern string -> AST (incl. {m,n} desugaring)
  predicates.py   AST leaf -> character-predicate, shared by both engines
  nfa.py          Thompson's construction: AST -> NFA
  simulate.py     NFA simulation (the "no backtracking" engine)
  backtrack.py    naive AST-walking backtracking matcher (the "for comparison" engine)
  api.py          re-flavored Regex/Match/compile/match/search/findall/finditer
  cli.py          `regrep` CLI
tests/            pytest suite -- includes cross-checking both engines against
                  Python's own `re` module on curated unambiguous patterns
benchmarks/       catastrophic_backtracking.py: nfa vs. backtrack timing demo
```

## Testing

```bash
pytest                    # 171 tests
python -m pyflakes src/ tests/ benchmarks/    # lint: clean
python benchmarks/catastrophic_backtracking.py
```

The test suite leans heavily on Python's built-in `re` module as a
correctness oracle: for a curated list of patterns where leftmost-first
and leftmost-longest matching necessarily agree (no ambiguity in the
patterns/inputs chosen), both `nfa` and `backtrack` engines are asserted
to produce output identical to `re.finditer`/`re.match` -- not just
"looks right", but byte-for-byte matching an independent, battle-tested
implementation. Where the two disciplines genuinely diverge, that's
called out in its own test (`test_leftmost_longest_vs_leftmost_first`)
rather than hidden.

Also covered: parser error cases (unbalanced parens, bad character
ranges, trailing backslash, `{4,2}` bad bounds, and more), the
empty-match infinite-loop guard in the backtracking repeater (`(a*)*`
must terminate immediately, not hang), NFA state-count staying linear
in pattern length even through `{m,n}` desugaring, and the full CLI
(all flags, stdin, multi-file, error exit codes).

## Current status

**Complete, tested v1.** Both engines are implemented, cross-validated
against each other and against Python's `re`, and wired up to the same
public API and the `regrep` CLI. 171 tests passing, `pyflakes`-clean.

### Roadmap / explicitly out of scope for v1

* **Capturing groups.** `(...)` currently only affects precedence during
  parsing -- `ast_nodes.Group` has an `index` field reserved for this,
  unused. Adding real capture support to the NFA engine means moving
  from plain Thompson simulation to a tagged/"Pike's VM" style
  simulation that tracks submatch positions per thread; the backtracking
  engine could get it more directly. Left for a follow-up rather than
  rushed into v1.
* **Anchors** (`^`, `$`) and **word boundaries** (`\b`). Not implemented;
  a `\b`-shaped pattern in `tests/cases.py` was deliberately avoided
  rather than faked.
* **Lazy quantifiers** (`*?`, `+?`) and **backreferences** (`\1`) --
  backreferences in particular aren't expressible by finite automata at
  all, so they'd only ever work in the backtracking engine.
* Unanchored `search()` is currently `O(n)` NFA-simulations, one per
  start position (so `O(n * m)` per search in the worst case) rather
  than the classic linear-time "prepend `.*?`" trick real engines use
  for unanchored search -- correct, but not the most efficient possible
  approach. Documented here rather than silently accepted as free
  performance no one asked about.

## License

MIT -- see [LICENSE](LICENSE).
