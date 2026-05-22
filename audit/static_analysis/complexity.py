"""Cyclomatic complexity (simplified McCabe).

Per spec: count only `if`, `else if`. Base = 1. `else` does NOT add.
Implemented at the token level to avoid double counting things inside strings
or comments — the parser already provides a noise-stripped method body.
"""
from __future__ import annotations

import re
from typing import List

from ..models import ClassInfo, ComplexityResult, MethodInfo


# `else if` first, then standalone `if`.
_ELSE_IF_RE = re.compile(r"\belse\s+if\b")
_IF_RE = re.compile(r"\bif\s*\(")


def _classify(value: float) -> str:
    if value <= 5:
        return "Baixa"
    if value <= 10:
        return "Média"
    if value <= 20:
        return "Alta"
    return "Crítica"


def compute_method_complexity(method: MethodInfo) -> int:
    body = method.body or ""
    if not body:
        return 1
    else_ifs = len(_ELSE_IF_RE.findall(body))
    # All `if (` occurrences include those that are part of `else if (`.
    total_ifs = len(_IF_RE.findall(body))
    # Per spec: each `if` adds +1, each `else if` adds +1, base = 1.
    # `else if` is matched by both regexes — count it once (as `else if`), not twice.
    standalone_ifs = total_ifs - else_ifs
    return 1 + standalone_ifs + else_ifs


def analyze(classes: List[ClassInfo]) -> ComplexityResult:
    method_rows = []
    class_rows = []
    totals = 0
    method_count = 0
    for cls in classes:
        cls_total = 0
        for m in cls.methods:
            cc = compute_method_complexity(m)
            m.cyclomatic_complexity = cc
            cls_total += cc
            method_count += 1
            method_rows.append({
                "class": cls.name,
                "method": m.name,
                "file": cls.file_path,
                "line": m.start_line,
                "complexity": cc,
                "classification": _classify(cc),
            })
        class_rows.append({
            "class": cls.name,
            "file": cls.file_path,
            "methods": len(cls.methods),
            "complexity_total": cls_total,
            "complexity_avg": round(cls_total / len(cls.methods), 2) if cls.methods else 0.0,
        })
        totals += cls_total

    method_rows.sort(key=lambda r: r["complexity"], reverse=True)
    class_rows.sort(key=lambda r: r["complexity_total"], reverse=True)
    critical_files = sorted({
        r["file"] for r in method_rows if r["complexity"] > 20
    })
    avg = totals / method_count if method_count else 0.0
    return ComplexityResult(
        total=totals,
        average=round(avg, 2),
        by_method=method_rows[:30],
        by_class=class_rows[:30],
        critical_files=critical_files,
        classification=_classify(avg),
    )
