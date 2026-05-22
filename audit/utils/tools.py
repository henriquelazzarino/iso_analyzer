"""Resolve Maven/Gradle executables — checks local tools/ folder before PATH.

Convention: place Maven at   <project_root>/tools/maven/   (any version)
            place Gradle at  <project_root>/tools/gradle/  (any version)

The tool searches for the binary inside these directories automatically,
so the user only needs to extract the zip — no PATH changes required.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List

# Root of THIS tool (the audit project directory)
_TOOL_ROOT = Path(__file__).resolve().parents[2]

_java_home_cache: Optional[str] = None


def _clean_java_home(path: str) -> str:
    """Strip trailing /bin or \\bin — JAVA_HOME must be the JDK root."""
    p = Path(path)
    if p.name.lower() == "bin":
        return str(p.parent)
    return path


def detect_java_home() -> Optional[str]:
    """Derive JAVA_HOME from the `java` executable if not already set."""
    global _java_home_cache
    if _java_home_cache is not None:
        return _java_home_cache

    # 1. Already set — validate and strip trailing /bin if needed
    existing = os.environ.get("JAVA_HOME", "")
    if existing:
        cleaned = _clean_java_home(existing)
        if Path(cleaned).is_dir() and (Path(cleaned) / "bin").exists():
            _java_home_cache = cleaned
            return _java_home_cache

    # 2. Derive from `java -XshowSettings:properties -version`
    java_exec = shutil.which("java")
    if not java_exec:
        return None
    try:
        result = subprocess.run(
            [java_exec, "-XshowSettings:properties", "-version"],
            capture_output=True, text=True, timeout=15, errors="replace",
        )
        for line in (result.stdout + result.stderr).splitlines():
            if "java.home" in line:
                raw = line.split("=", 1)[-1].strip()
                home = _clean_java_home(raw)
                p = Path(home)
                if p.is_dir() and (p / "bin").exists():
                    _java_home_cache = str(p)
                    return _java_home_cache
    except Exception:  # noqa: BLE001
        pass

    # 3. Fallback: resolve symlink of java binary → parent of bin/
    try:
        resolved = Path(java_exec).resolve()
        # typical layout: <JAVA_HOME>/bin/java[.exe]
        home = str(resolved.parent.parent)
        home = _clean_java_home(home)
        p = Path(home)
        if p.is_dir() and (p / "bin").exists():
            _java_home_cache = str(p)
            return _java_home_cache
    except Exception:  # noqa: BLE001
        pass

    return None


def _java_major_version() -> int:
    """Return the major JDK version (8, 11, 17, 21 …) or 0 on failure."""
    java = shutil.which("java")
    if not java:
        return 0
    try:
        r = subprocess.run(
            [java, "-version"], capture_output=True, text=True,
            timeout=10, errors="replace",
        )
        import re
        # "java version "11.0.2"" or "openjdk version "21.0.1""
        m = re.search(r'"(\d+)[\._]', r.stderr + r.stdout)
        if m:
            major = int(m.group(1))
            return 9 if major == 1 else major  # "1.8" → 8 represented as 9 fallback
    except Exception:  # noqa: BLE001
        pass
    return 0


# --add-opens required for old Lombok / annotation processors on JDK 17+
# This is the comprehensive set covering all internal javac packages Lombok touches.
_LOMBOK_ADD_OPENS = " ".join([
    "--add-opens=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.code=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.comp=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.jvm=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.main=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.model=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.parser=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.processing=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac.nio=ALL-UNNAMED",
    "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "--add-opens=java.base/java.util=ALL-UNNAMED",
])


def build_env_with_java() -> dict:
    """Return a copy of os.environ with JAVA_HOME and MAVEN_OPTS set."""
    env = os.environ.copy()
    if not env.get("JAVA_HOME"):
        home = detect_java_home()
        if home:
            env["JAVA_HOME"] = home
    # Inject --add-opens for JDK 16+ so old Lombok / annotation processors work
    major = _java_major_version()
    if major >= 16:
        existing = env.get("MAVEN_OPTS", "")
        if "--add-opens=jdk.compiler" not in existing:
            env["MAVEN_OPTS"] = (existing + " " + _LOMBOK_ADD_OPENS).strip()
    return env


def _find_local_mvn() -> Optional[Path]:
    """Return path to mvn(.cmd) inside tools/maven/ if it exists."""
    tools_maven = _TOOL_ROOT / "tools" / "maven"
    if not tools_maven.exists():
        return None
    # Maven bin directory contains mvn / mvn.cmd
    for candidate in tools_maven.rglob("mvn.cmd" if os.name == "nt" else "mvn"):
        if candidate.is_file():
            return candidate
    return None


def _find_local_gradle() -> Optional[Path]:
    """Return path to gradle(.bat) inside tools/gradle/ if it exists."""
    tools_gradle = _TOOL_ROOT / "tools" / "gradle"
    if not tools_gradle.exists():
        return None
    name = "gradle.bat" if os.name == "nt" else "gradle"
    for candidate in tools_gradle.rglob(name):
        if candidate.is_file():
            return candidate
    return None


def resolve_mvn() -> Optional[List[str]]:
    """Return an mvn command list, preferring local tools/ over PATH."""
    local = _find_local_mvn()
    if local:
        return [str(local)]
    if shutil.which("mvn"):
        return ["mvn"]
    return None


def resolve_gradle_system() -> Optional[List[str]]:
    """Return a system-level gradle command, preferring local tools/ over PATH."""
    local = _find_local_gradle()
    if local:
        return [str(local)]
    if shutil.which("gradle"):
        return ["gradle"]
    return None


def tools_status() -> dict:
    """Return a dict describing which tools were found and where."""
    mvn_local = _find_local_mvn()
    gradle_local = _find_local_gradle()
    return {
        "mvn_local": str(mvn_local) if mvn_local else None,
        "mvn_path": bool(shutil.which("mvn")),
        "gradle_local": str(gradle_local) if gradle_local else None,
        "gradle_path": bool(shutil.which("gradle")),
        "java_path": bool(shutil.which("java")),
        "javac_path": bool(shutil.which("javac")),
        "git_path": bool(shutil.which("git")),
    }
