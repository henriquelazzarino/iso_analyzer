"""Coupling Between Objects (CBO).

For each class, count distinct external types it depends on, drawing from:
- imports (excluding java.lang.* and own package)
- referenced PascalCase identifiers in the body (instantiations, types, calls)

We deduplicate by short type name (e.g. `UserService`), which is what the spec
asks for ("each unique class used"). Generic parameters, primitives and the
class itself are excluded.
"""
from __future__ import annotations

from typing import List

from ..models import ClassInfo, CouplingResult


_IGNORED_IMPORT_PREFIXES = ("java.lang.",)


def _short_name(fqn: str) -> str:
    if not fqn:
        return ""
    # Drop wildcard
    if fqn.endswith(".*"):
        return ""
    return fqn.rsplit(".", 1)[-1]


def _classify(value: float) -> str:
    if value <= 5:
        return "Bom"
    if value <= 10:
        return "Moderado"
    if value <= 20:
        return "Alto"
    return "Crítico"


def analyze(classes: List[ClassInfo]) -> CouplingResult:
    rows = []
    total = 0
    own_names = {c.name for c in classes}
    for cls in classes:
        deps = set()
        for imp in cls.imports:
            if any(imp.startswith(p) for p in _IGNORED_IMPORT_PREFIXES):
                continue
            short = _short_name(imp)
            if short and short != cls.name:
                deps.add(short)
        for ref in cls.referenced_types:
            if ref != cls.name and ref not in own_names_only(cls, classes):
                # Keep external references even if not imported (same package types).
                deps.add(ref)
        # Re-add same-package own types but exclude the class itself
        # (already excluded above).
        cbo = len(deps)
        total += cbo
        rows.append({
            "class": cls.name,
            "file": cls.file_path,
            "cbo": cbo,
            "classification": _classify(cbo),
            "dependencies": sorted(deps)[:25],
        })
    rows.sort(key=lambda r: r["cbo"], reverse=True)
    avg = total / len(rows) if rows else 0.0
    critical = [r["class"] for r in rows if r["cbo"] > 20]
    return CouplingResult(
        average=round(avg, 2),
        by_class=rows[:30],
        critical_classes=critical,
        classification=_classify(avg),
    )


def own_names_only(_: ClassInfo, classes: List[ClassInfo]) -> set:
    # Helper kept separate to avoid recomputing per call; cheap for typical projects.
    return {c.name for c in classes}
