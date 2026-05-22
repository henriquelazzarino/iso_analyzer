"""Detect test framework usage and test file counts."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from ..utils import safe_read, walk_files


_JUNIT_RE = re.compile(r"\borg\.junit\.|@Test\b|jupiter\.api")
_TESTNG_RE = re.compile(r"\borg\.testng\.|@org\.testng\.annotations")


def detect(root: Path) -> Tuple[str, int]:
    """Return (framework, test_file_count). framework ∈ {junit, testng, none}."""
    junit = 0
    testng = 0
    test_files: List[Path] = []
    for f in walk_files(root, [".java"]):
        # Heuristic: live under a test directory OR end with Test/Tests/IT
        path_str = str(f).replace("\\", "/").lower()
        is_test_path = "/test/" in path_str or "/tests/" in path_str
        name = f.stem
        is_test_name = name.endswith(("Test", "Tests", "IT", "TestCase"))
        if not (is_test_path or is_test_name):
            continue
        src = safe_read(f)
        if not src:
            continue
        test_files.append(f)
        if _JUNIT_RE.search(src):
            junit += 1
        elif _TESTNG_RE.search(src):
            testng += 1
    if junit >= testng and junit > 0:
        return "junit", len(test_files)
    if testng > 0:
        return "testng", len(test_files)
    return "none", len(test_files)
