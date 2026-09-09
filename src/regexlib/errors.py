"""Exceptions raised by regexlib."""


class RegexSyntaxError(ValueError):
    """Raised when a pattern string cannot be parsed.

    Carries the offending position so callers (and the CLI) can point
    at exactly where the pattern went wrong.
    """

    def __init__(self, message: str, pattern: str, pos: int):
        self.message = message
        self.pattern = pattern
        self.pos = pos
        pointer = " " * pos + "^"
        super().__init__(f"{message} (at position {pos})\n  {pattern}\n  {pointer}")
