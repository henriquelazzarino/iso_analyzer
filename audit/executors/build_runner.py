"""Build runner — detects Maven/Gradle and invokes them safely."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from ..core import get_logger
from ..utils import find_first, resolve_mvn, resolve_gradle_system, build_env_with_java

log = get_logger()


def detect_build_system(root: Path) -> str:
    """Return 'maven' | 'gradle' | 'none'."""
    if find_first(root, ["pom.xml"]):
        return "maven"
    if find_first(root, ["build.gradle", "build.gradle.kts"]):
        return "gradle"
    return "none"


def _resolve_maven() -> Optional[List[str]]:
    return resolve_mvn()


def _resolve_gradle(root: Path) -> Optional[List[str]]:
    # Prefer the project wrapper if present
    wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if wrapper.exists():
        try:
            if os.name != "nt":
                os.chmod(wrapper, 0o755)
        except OSError:
            pass
        return [str(wrapper)]
    # Fall back to local tools/ or system gradle
    return resolve_gradle_system()


def _project_root_for(root: Path, marker: str) -> Path:
    """If marker exists at a deeper directory, use it as cwd."""
    p = find_first(root, [marker])
    return p.parent if p else root


def run_tests(root: Path, timeout: int = 600) -> Tuple[bool, str, Path]:
    """Run the project's test suite and produce coverage if possible.

    Returns (success, log_text, effective_root).
    """
    from ..executors.app_runner import _inject_jvm_config
    system = detect_build_system(root)
    if system == "maven":
        cwd = _project_root_for(root, "pom.xml")
        _inject_jvm_config(cwd)
        cmd = _resolve_maven()
        if not cmd:
            return False, "mvn not found on PATH", cwd
        from ..executors.app_runner import _lombok_version_override
        lombok_flag = _lombok_version_override(root)
        full = cmd + [
            "-B", "-q",
            "test",
            "org.jacoco:jacoco-maven-plugin:0.8.11:report",
            "-Dmaven.test.failure.ignore=true",
        ] + ([lombok_flag] if lombok_flag else [])
        return _run(full, cwd, timeout)
    if system == "gradle":
        cwd = _project_root_for(root, "build.gradle") or _project_root_for(root, "build.gradle.kts")
        cmd = _resolve_gradle(cwd)
        if not cmd:
            return False, "gradle not found and no wrapper present", cwd
        full = cmd + ["test", "jacocoTestReport", "--no-daemon", "--continue"]
        return _run(full, cwd, timeout)
    return False, "no Maven/Gradle build detected", root


def _run(cmd: List[str], cwd: Path, timeout: int) -> Tuple[bool, str, Path]:
    log.info("Running %s (cwd=%s)", " ".join(cmd), cwd)
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, errors="replace",
            env=build_env_with_java(),
        )
        out = (result.stdout or "") + "\n" + (result.stderr or "")
        log.debug("Build output (tail): %s", out[-1500:])
        return result.returncode == 0, out[-8000:], cwd
    except subprocess.TimeoutExpired:
        return False, f"Build timed out after {timeout}s", cwd
    except FileNotFoundError as exc:
        return False, f"Executable not found: {exc}", cwd
    except Exception as exc:  # noqa: BLE001
        return False, f"Unexpected build error: {exc}", cwd
