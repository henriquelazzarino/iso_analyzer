"""Filesystem helpers — robust walks and reads tolerant to encoding errors."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator, List, Optional


SKIP_DIRS = {
    ".git", ".idea", ".vscode", ".gradle", ".mvn", ".settings",
    "target", "build", "out", "node_modules", "bin", "dist",
    "__pycache__", ".tmp_clones",
}


def safe_read(path: Path, max_bytes: int = 5 * 1024 * 1024) -> str:
    """Read a file with multiple encoding fallbacks. Returns '' on failure."""
    try:
        if path.stat().st_size > max_bytes:
            return ""
    except OSError:
        return ""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc, errors="strict") as fh:
                return fh.read()
        except (UnicodeDecodeError, OSError):
            continue
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def walk_files(root: Path, extensions: Optional[List[str]] = None) -> Iterator[Path]:
    """Yield files under root, skipping build/VCS directories."""
    if not root.exists():
        return
    exts = tuple(extensions) if extensions else None
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if exts and not fn.endswith(exts):
                continue
            yield Path(dirpath) / fn


def find_first(root: Path, names: List[str]) -> Optional[Path]:
    """Return the first matching file by basename anywhere in the tree."""
    target = set(names)
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in target:
                return Path(dirpath) / fn
    return None


def find_all(root: Path, names: List[str]) -> List[Path]:
    target = set(names)
    out: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in target:
                out.append(Path(dirpath) / fn)
    return out


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
