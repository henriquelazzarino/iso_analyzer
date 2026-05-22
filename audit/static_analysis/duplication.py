"""Duplication detection (DRYness).

Algorithm: rolling hash over consecutive non-empty normalized lines (>= window).
Lines are normalized (whitespace collapsed, comments stripped via the parser
input). Blocks of >= 5 identical consecutive lines that occur in two or more
locations are reported.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Tuple

from ..models import DuplicationResult
from ..parsers import strip_noise
from ..utils import safe_read


WINDOW = 5


def _normalize(line: str) -> str:
    # Collapse internal whitespace; treat tabs/spaces equivalently.
    return " ".join(line.split())


def _hash(block: List[str]) -> str:
    return hashlib.md5("\n".join(block).encode("utf-8", errors="ignore")).hexdigest()


def analyze(files: List[Path]) -> DuplicationResult:
    # block_hash -> list of (file, start_line)
    occurrences: Dict[str, List[Tuple[str, int]]] = {}
    block_sample: Dict[str, str] = {}
    total_lines = 0
    for f in files:
        try:
            raw = safe_read(f)
            if not raw:
                continue
            clean = strip_noise(raw)
            lines = clean.splitlines()
            total_lines += len([ln for ln in lines if ln.strip()])
            normalized = [_normalize(ln) for ln in lines]
            n = len(normalized)
            for i in range(0, n - WINDOW + 1):
                window = normalized[i: i + WINDOW]
                if any(not w for w in window):
                    continue  # skip blank-containing windows
                # Skip trivial blocks (e.g. closing braces)
                joined = "".join(window).strip()
                if len(joined) < 30:
                    continue
                h = _hash(window)
                occurrences.setdefault(h, []).append((str(f), i + 1))
                if h not in block_sample:
                    block_sample[h] = "\n".join(window)
        except Exception:  # noqa: BLE001
            continue

    samples: List[Dict] = []
    duplicated_lines = 0
    duplicated_blocks = 0
    for h, locs in occurrences.items():
        if len(locs) < 2:
            continue
        duplicated_blocks += 1
        duplicated_lines += WINDOW * (len(locs) - 1)
        if len(samples) < 20:
            samples.append({
                "hash": h[:10],
                "occurrences": len(locs),
                "locations": [{"file": f, "line": ln} for f, ln in locs[:5]],
                "sample": block_sample[h],
            })
    pct = (duplicated_lines / total_lines * 100.0) if total_lines else 0.0
    samples.sort(key=lambda s: s["occurrences"], reverse=True)
    return DuplicationResult(
        duplicated_blocks=duplicated_blocks,
        duplicated_lines=duplicated_lines,
        total_lines=total_lines,
        percentage=round(pct, 2),
        samples=samples,
    )
