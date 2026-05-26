"""Coverage extraction — prefers JaCoCo XML reports under target/site or build/reports."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple

from ..core import get_logger

log = get_logger()


_JACOCO_NAMES = {"jacoco.xml", "jacocoTestReport.xml"}

# Known paths where JaCoCo generates XML reports
_KNOWN_JACOCO_PATHS = [
    "target/site/jacoco/jacoco.xml",
    "target/site/jacoco-ut/jacoco.xml",
    "target/site/jacoco-it/jacoco.xml",
    "build/reports/jacoco/test/jacocoTestReport.xml",
    "build/reports/jacoco/jacocoTestReport.xml",
]


def find_jacoco_reports(root: Path) -> List[Path]:
    """Find JaCoCo XML reports. Uses a dedicated walk that does NOT skip
    target/build directories, since that's exactly where JaCoCo outputs live."""
    out: List[Path] = []

    # 1. Check well-known paths first (fast, no full walk needed)
    for rel in _KNOWN_JACOCO_PATHS:
        candidate = root / rel
        if candidate.is_file():
            out.append(candidate)

    # 2. Also check submodules (multi-module Maven/Gradle projects)
    #    Walk the tree including target/build dirs, but only look for jacoco XMLs
    for dirpath, dirnames, filenames in os.walk(str(root)):
        # Skip VCS/IDE dirs but NOT build output dirs
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in {"node_modules", "__pycache__", ".tmp_clones"}
        ]
        for fn in filenames:
            if fn in _JACOCO_NAMES:
                p = Path(dirpath) / fn
                if p not in out:
                    out.append(p)

    return out


def parse_jacoco(xml_path: Path) -> Optional[Tuple[float, float]]:
    """Return (line_coverage_pct, branch_coverage_pct) or None on failure."""
    try:
        # Disable DTD resolution to avoid network lookups / XXE.
        parser = ET.XMLParser()
        tree = ET.parse(str(xml_path), parser=parser)
        root = tree.getroot()
    except Exception as exc:  # noqa: BLE001
        log.debug("Failed to parse %s: %s", xml_path, exc)
        return None
    # JaCoCo: <counter type="LINE" missed="x" covered="y"/> at root level (project totals).
    line_pct = 0.0
    branch_pct = 0.0
    for counter in root.findall("./counter"):
        try:
            missed = int(counter.attrib.get("missed", "0"))
            covered = int(counter.attrib.get("covered", "0"))
            total = missed + covered
            pct = (covered / total * 100.0) if total else 0.0
        except (ValueError, TypeError):
            continue
        ctype = counter.attrib.get("type", "").upper()
        if ctype == "LINE":
            line_pct = pct
        elif ctype == "BRANCH":
            branch_pct = pct
    return line_pct, branch_pct


def classify(pct: float) -> str:
    if pct >= 80:
        return "Excelente"
    if pct >= 60:
        return "Boa"
    if pct >= 40:
        return "Ruim"
    return "Crítica"


def collect(root: Path) -> Tuple[float, float, str]:
    """Walk for JaCoCo XMLs and return best (line, branch, source_path)."""
    best = (0.0, 0.0, "")
    for xml in find_jacoco_reports(root):
        parsed = parse_jacoco(xml)
        if parsed is None:
            continue
        line, branch = parsed
        if line > best[0]:
            best = (line, branch, str(xml))
    return best
