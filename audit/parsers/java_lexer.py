"""Minimal Java lexer/normalizer.

Goal: strip noise (comments, strings) deterministically while preserving line
numbers. This is the foundation for the manual parser and downstream metrics
(complexity, coupling, duplication). It is intentionally NOT a full grammar —
we only need a structure that is robust enough to walk classes/methods and
count tokens.
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Comment/string stripping while preserving line numbers
# ---------------------------------------------------------------------------

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
# Strings: handle escaped quotes
_STRING_RE = re.compile(r'"(?:\\.|[^"\\\n])*"')
_CHAR_RE = re.compile(r"'(?:\\.|[^'\\\n])'")


def _replace_keep_newlines(match: "re.Match[str]") -> str:
    """Replace match with spaces, preserving '\\n' so line numbers stay aligned."""
    text = match.group(0)
    return "".join("\n" if ch == "\n" else " " for ch in text)


def strip_noise(source: str) -> str:
    """Remove comments, strings and chars, preserving line numbers."""
    if not source:
        return ""
    try:
        out = _BLOCK_COMMENT_RE.sub(_replace_keep_newlines, source)
        out = _LINE_COMMENT_RE.sub(_replace_keep_newlines, out)
        out = _STRING_RE.sub(_replace_keep_newlines, out)
        out = _CHAR_RE.sub(_replace_keep_newlines, out)
        return out
    except re.error:
        return source


# ---------------------------------------------------------------------------
# Brace matching
# ---------------------------------------------------------------------------

def find_matching_brace(text: str, open_pos: int) -> int:
    """Return index of the brace matching '{' at `open_pos`, or -1."""
    if open_pos < 0 or open_pos >= len(text) or text[open_pos] != "{":
        return -1
    depth = 0
    i = open_pos
    n = len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def line_of(text: str, pos: int) -> int:
    """1-based line number for `pos`."""
    if pos <= 0:
        return 1
    return text.count("\n", 0, pos) + 1
