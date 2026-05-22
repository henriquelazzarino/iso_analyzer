"""Git acquisition helpers — uses the system `git` command if available."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..core import get_logger

log = get_logger()


def is_git_url(source: str) -> bool:
    s = source.strip().lower()
    return (
        s.startswith("http://")
        or s.startswith("https://")
        or s.startswith("git@")
        or s.startswith("ssh://")
        or s.endswith(".git")
    )


def project_name_from_url(url: str) -> str:
    base = url.rstrip("/").split("/")[-1]
    if base.endswith(".git"):
        base = base[:-4]
    return base or "repository"


def clone(url: str, dest_root: Path, timeout: int = 300) -> Optional[Path]:
    """Clone `url` shallowly into `dest_root/<name>`. Returns the path or None."""
    if shutil.which("git") is None:
        log.error("git executable not found in PATH")
        return None
    name = project_name_from_url(url)
    dest = dest_root / name
    if dest.exists():
        # Reuse existing
        log.info("Reusing existing clone at %s", dest)
        return dest
    dest_root.mkdir(parents=True, exist_ok=True)
    log.info("Cloning %s -> %s", url, dest)
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            log.error("git clone failed: %s", result.stderr.strip()[:500])
            return None
        # Remove .git so the clone has no git tracking — prevents VS Code from
        # showing audit modifications (pom.xml patches, .mvn/jvm.config) as
        # uncommitted changes inside a nested repository.
        git_dir = dest / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir, ignore_errors=True)
        return dest
    except subprocess.TimeoutExpired:
        log.error("git clone timed out after %ss", timeout)
        return None
    except Exception as exc:  # noqa: BLE001
        log.error("git clone unexpected error: %s", exc)
        return None
