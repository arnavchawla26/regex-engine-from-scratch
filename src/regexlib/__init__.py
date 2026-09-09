"""regexlib: a small regex engine built from scratch.

Public API lives in :mod:`regexlib.api`. See the top-level README for
design notes on the two matching engines (Thompson NFA simulation vs.
naive backtracking) and the tradeoffs between them.
"""

from .api import Regex, compile, match, search, findall, finditer
from .errors import RegexSyntaxError

__all__ = [
    "Regex",
    "compile",
    "match",
    "search",
    "findall",
    "finditer",
    "RegexSyntaxError",
]

__version__ = "0.1.0"
