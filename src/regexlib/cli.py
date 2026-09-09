"""``regrep``: a small grep-like CLI built on top of regexlib.

    regrep [-i] [-n] [-c] [-v] [-o] [--engine {nfa,backtrack}] PATTERN [FILE ...]

Reads from the given files, or stdin if none are given, and prints
lines that match PATTERN -- same basic contract as POSIX grep, minus
the many, many flags real grep has. Exit status follows grep's
convention: 0 if at least one match was found, 1 if none was, 2 on a
usage/pattern/file error.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, TextIO

from .api import Regex
from .errors import RegexSyntaxError


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="regrep",
        description="Search files (or stdin) for lines matching a regexlib pattern.",
    )
    p.add_argument("pattern", help="pattern to search for (regexlib syntax, see README)")
    p.add_argument("files", nargs="*", help="files to search (default: stdin)")
    p.add_argument("-i", "--ignore-case", action="store_true", help="case-insensitive match")
    p.add_argument("-n", "--line-number", action="store_true", help="prefix output with line numbers")
    p.add_argument("-c", "--count", action="store_true", help="print only a count of matching lines")
    p.add_argument("-v", "--invert-match", action="store_true", help="print non-matching lines")
    p.add_argument("-o", "--only-matching", action="store_true", help="print only the matched text, not the whole line")
    p.add_argument(
        "--engine",
        choices=["nfa", "backtrack"],
        default="nfa",
        help="matching engine to use (default: nfa)",
    )
    return p


def _iter_lines(path: Optional[str]) -> List[str]:
    if path is None or path == "-":
        return sys.stdin.read().splitlines()
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def run(argv: Optional[List[str]] = None, stdout: TextIO = None, stderr: TextIO = None) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    args = build_arg_parser().parse_args(argv)

    try:
        regex = Regex(args.pattern, ignorecase=args.ignore_case, engine=args.engine)
    except RegexSyntaxError as exc:
        print(f"regrep: bad pattern: {exc}", file=stderr)
        return 2

    sources = args.files if args.files else [None]
    multiple_sources = len(sources) > 1
    any_match = False
    had_error = False

    for source in sources:
        label = source if source is not None else "(standard input)"
        try:
            lines = _iter_lines(source)
        except OSError as exc:
            print(f"regrep: {label}: {exc.strerror}", file=stderr)
            had_error = True
            continue

        match_count = 0
        for lineno, line in enumerate(lines, start=1):
            found = regex.search(line)
            is_match = found is not None
            if is_match != args.invert_match:
                match_count += 1
                any_match = True
                if args.count:
                    continue
                if args.only_matching:
                    # -o prints every match on the line, one per output
                    # line, not just the first -- same as real grep -o.
                    for m in regex.finditer(line):
                        _print_hit(
                            stdout,
                            label=label,
                            show_label=multiple_sources,
                            lineno=lineno,
                            show_lineno=args.line_number,
                            line=line,
                            only_matching=True,
                            match_text=m.group(),
                        )
                else:
                    _print_hit(
                        stdout,
                        label=label,
                        show_label=multiple_sources,
                        lineno=lineno,
                        show_lineno=args.line_number,
                        line=line,
                        only_matching=False,
                        match_text="",
                    )
        if args.count:
            prefix = f"{label}:" if multiple_sources else ""
            print(f"{prefix}{match_count}", file=stdout)

    if had_error:
        return 2
    return 0 if any_match else 1


def _print_hit(
    stdout: TextIO,
    *,
    label: str,
    show_label: bool,
    lineno: int,
    show_lineno: bool,
    line: str,
    only_matching: bool,
    match_text: str,
) -> None:
    parts = []
    if show_label:
        parts.append(f"{label}:")
    if show_lineno:
        parts.append(f"{lineno}:")
    parts.append(match_text if only_matching else line)
    print("".join(parts), file=stdout)


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
