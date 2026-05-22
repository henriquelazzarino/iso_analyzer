"""Manual Java parser — produces ClassInfo objects without an AST library.

Strategy
--------
1. Strip comments/strings (`java_lexer.strip_noise`) preserving line numbers.
2. Regex-locate `package`, `import`, and type declarations.
3. For each class/interface/enum/record, slice the brace-matched body and
   regex-locate method headers within it, then brace-match the body.
4. Collect referenced type names (PascalCase identifiers + imports) for CBO.

This is intentionally conservative: when something looks ambiguous we skip
gracefully rather than raising — robustness over completeness.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from ..models import ClassInfo, MethodInfo
from ..utils import safe_read
from .java_lexer import strip_noise, find_matching_brace, line_of


_PACKAGE_RE = re.compile(r"^\s*package\s+([\w\.]+)\s*;", re.MULTILINE)
_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w\.\*]+)\s*;", re.MULTILINE)

# Type declaration: class | interface | enum | record
# Captures the type kind, name, and position of the opening brace.
_TYPE_DECL_RE = re.compile(
    r"\b(class|interface|enum|record)\s+([A-Z_][A-Za-z0-9_]*)\b[^{;]*\{"
)

# Method header heuristic:
# [modifiers] [generic] return_type name(params) [throws ...] {
# We require: identifier followed by '(' then ')' eventually then '{'.
# This regex finds the candidate header start; we then validate with brace matching.
_METHOD_HEADER_RE = re.compile(
    r"""
    (?P<modifiers>(?:\b(?:public|private|protected|static|final|abstract|
                       synchronized|native|default|strictfp)\b\s+)*)
    (?:<[^>]+>\s+)?                                   # optional generics
    (?P<return>[\w\.\<\>\[\],\s\?]+?)                 # return type (lazy)
    \s+(?P<name>[a-zA-Z_][A-Za-z0-9_]*)\s*
    \(
    """,
    re.VERBOSE,
)

# Reserved keywords that look like method names — must be excluded.
_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "new", "throw",
    "synchronized", "try", "do", "else", "case", "break", "continue",
    "instanceof", "super", "this", "assert", "yield",
}

# PascalCase identifiers used to extract referenced types for CBO.
_TYPE_REF_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\b")

_JAVA_BUILTINS = {
    "String", "Object", "Integer", "Long", "Double", "Float", "Boolean",
    "Byte", "Short", "Character", "Number", "Math", "System", "Class",
    "Void", "Exception", "RuntimeException", "Throwable", "Error",
    "Override", "Deprecated", "SuppressWarnings", "FunctionalInterface",
    "SafeVarargs", "Nullable", "NonNull",
}


def _balanced_paren_end(text: str, open_pos: int) -> int:
    """Return index of ')' matching '(' at open_pos, or -1."""
    if open_pos < 0 or open_pos >= len(text) or text[open_pos] != "(":
        return -1
    depth = 0
    i = open_pos
    n = len(text)
    while i < n:
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _extract_methods(body: str, body_start_line: int) -> List[MethodInfo]:
    """Find methods within a class body. `body` excludes the outer braces."""
    methods: List[MethodInfo] = []
    pos = 0
    n = len(body)
    while pos < n:
        m = _METHOD_HEADER_RE.search(body, pos)
        if not m:
            break
        name = m.group("name")
        ret = m.group("return").strip()
        # Skip false positives
        if name in _KEYWORDS or ret in _KEYWORDS:
            pos = m.end()
            continue
        # The header capture ends right at '('. Walk to its matching ')'.
        paren_open = m.end() - 1  # position of '('
        paren_close = _balanced_paren_end(body, paren_open)
        if paren_close < 0:
            pos = m.end()
            continue
        # Find the next '{' or ';' (abstract/interface method)
        tail_start = paren_close + 1
        # Skip 'throws ...' until '{' or ';'
        i = tail_start
        while i < n and body[i] not in "{;":
            i += 1
        if i >= n:
            break
        if body[i] == ";":
            # Abstract / interface method — count as method with complexity 1
            start_line = body_start_line + body.count("\n", 0, m.start())
            methods.append(MethodInfo(
                name=name,
                start_line=start_line,
                end_line=start_line,
                body="",
                cyclomatic_complexity=1,
            ))
            pos = i + 1
            continue
        # body[i] == '{'
        brace_end = find_matching_brace(body, i)
        if brace_end < 0:
            break
        method_body = body[i + 1: brace_end]
        start_line = body_start_line + body.count("\n", 0, m.start())
        end_line = body_start_line + body.count("\n", 0, brace_end)
        methods.append(MethodInfo(
            name=name,
            start_line=start_line,
            end_line=end_line,
            body=method_body,
        ))
        pos = brace_end + 1
    return methods


def _extract_referenced_types(text: str, own_names: set) -> List[str]:
    refs: set = set()
    for m in _TYPE_REF_RE.finditer(text):
        name = m.group(1)
        if name in own_names or name in _JAVA_BUILTINS:
            continue
        refs.add(name)
    return sorted(refs)


def parse_java_source(file_path: Path, source: Optional[str] = None) -> List[ClassInfo]:
    """Parse one Java file. Always returns a list (possibly empty)."""
    try:
        if source is None:
            source = safe_read(file_path)
        if not source:
            return []
        clean = strip_noise(source)
        package_match = _PACKAGE_RE.search(clean)
        package = package_match.group(1) if package_match else ""
        imports = [m.group(1) for m in _IMPORT_RE.finditer(clean)]
        classes: List[ClassInfo] = []
        # Track own declared type names to exclude self-refs from CBO
        decls = list(_TYPE_DECL_RE.finditer(clean))
        own_names = {m.group(2) for m in decls}
        for m in decls:
            class_name = m.group(2)
            brace_pos = m.end() - 1  # position of '{'
            brace_end = find_matching_brace(clean, brace_pos)
            if brace_end < 0:
                continue
            body = clean[brace_pos + 1: brace_end]
            body_start_line = line_of(clean, brace_pos + 1)
            methods = _extract_methods(body, body_start_line)
            referenced = _extract_referenced_types(body, own_names | {class_name})
            classes.append(ClassInfo(
                name=class_name,
                file_path=str(file_path),
                package=package,
                imports=imports[:],
                methods=methods,
                referenced_types=referenced,
                line_count=clean.count("\n", brace_pos, brace_end) + 1,
            ))
        return classes
    except Exception:  # noqa: BLE001
        # Never let a single bad file kill the analysis.
        return []
