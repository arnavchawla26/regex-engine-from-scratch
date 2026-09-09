import re


def re_whole_matches(pattern: str, text: str):
    """List of whole-match strings from Python's `re`, used as an
    oracle. Deliberately not `re.findall`: when a pattern has capturing
    groups, `findall` returns the *group's* text instead of the whole
    match, which isn't what we want to compare against (our engines
    don't have capture groups at all yet -- see ast_nodes.Group)."""
    return [m.group(0) for m in re.finditer(pattern, text)]
