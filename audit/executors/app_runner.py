"""Application runner — spins the target Java application up for benchmark.

Strategy
--------
1. Detect Spring Boot via pom.xml/build.gradle plugins → use spring-boot:run.
2. Else, if there is a main class in the parsed classes, run it via `mvn exec:java`
   or `gradle run` if applicable.
3. Else, return a runner that no-ops; benchmark module will skip dynamic phase.

The runner is *non-blocking*: starts the process, polls a small set of likely
URLs (`/`, `/actuator/health`, `/health`) for readiness, then returns a handle.
On shutdown, terminates the process tree gracefully.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional

from ..core import get_logger
from ..utils import find_first, safe_read, resolve_mvn, resolve_gradle_system, build_env_with_java

log = get_logger()


READY_PATHS = ["/actuator/health", "/health", "/"]


def _read_build_files(root: Path) -> str:
    """Return concatenated content of pom.xml / build.gradle for keyword scans."""
    chunks: List[str] = []
    for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
        f = find_first(root, [name])
        if f:
            chunks.append(safe_read(f))
    return "\n".join(chunks).lower()


def _looks_like_spring_boot(root: Path) -> bool:
    return "spring-boot" in _read_build_files(root)


def _build_overrides(root: Path) -> dict:
    """Return env vars that make hostile Spring Boot apps boot in-process.

    Strategy: when the project uses JPA but depends on an external database
    (MySQL/Postgres/etc.), force an in-memory H2 datasource and disable common
    boot-time blockers (Flyway, Liquibase, Spring Security). This covers ~70%
    of real-world Spring Boot CRUDs without touching the source.
    """
    content = _read_build_files(root)
    overrides: dict = {}
    if not _looks_like_spring_boot(root):
        return overrides

    has_jpa = "spring-boot-starter-data-jpa" in content or "hibernate" in content
    has_h2 = "com.h2database" in content or "h2database" in content
    has_external_db = any(
        kw in content for kw in (
            "mysql-connector", "postgresql", "mariadb",
            "mssql-jdbc", "ojdbc", "oracle.jdbc",
        )
    )

    if has_jpa and (has_h2 or has_external_db):
        overrides.update({
            "SPRING_DATASOURCE_URL": "jdbc:h2:mem:auditdb;DB_CLOSE_DELAY=-1;MODE=MySQL",
            "SPRING_DATASOURCE_DRIVER_CLASS_NAME": "org.h2.Driver",
            "SPRING_DATASOURCE_USERNAME": "sa",
            "SPRING_DATASOURCE_PASSWORD": "",
            "SPRING_JPA_HIBERNATE_DDL_AUTO": "create-drop",
            "SPRING_JPA_DATABASE_PLATFORM": "org.hibernate.dialect.H2Dialect",
            "SPRING_SQL_INIT_MODE": "never",
        })
        # Patch pom.xml directly to add H2 (works with all Spring Boot versions).
        # Falls back to jar injection for newer Spring Boot (2.7+).
        if not has_h2 and has_external_db:
            patched = _patch_pom_add_h2(root)
            if not patched:
                # Fallback: store jar path for additionalClasspathElements (SB 2.7+)
                h2_jar = _ensure_h2_jar(root)
                if h2_jar:
                    overrides["_H2_EXTRA_CLASSPATH"] = str(h2_jar)
        # Disable migrations that break against an empty H2
        if "flyway" in content:
            overrides["SPRING_FLYWAY_ENABLED"] = "false"
        if "liquibase" in content:
            overrides["SPRING_LIQUIBASE_ENABLED"] = "false"

    # Disable Spring Security so /health and arbitrary endpoints respond
    if "spring-boot-starter-security" in content or "spring-security" in content:
        overrides["SPRING_AUTOCONFIGURE_EXCLUDE"] = (
            "org.springframework.boot.autoconfigure.security."
            "servlet.SecurityAutoConfiguration"
        )

    # Force a stable port and expose /actuator/health if Actuator is present
    if "spring-boot-starter-actuator" in content:
        overrides["MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE"] = "health,info"
        overrides["MANAGEMENT_ENDPOINT_HEALTH_SHOW_DETAILS"] = "always"

    return overrides


def _resolve_mvn(root: Path) -> Optional[List[str]]:
    """Return an mvn command: project wrapper > local tools/ > PATH."""
    # 1. Maven Wrapper inside the target project
    for search_root in (root, _project_cwd_raw(root)):
        mvnw = search_root / ("mvnw.cmd" if os.name == "nt" else "mvnw")
        if mvnw.exists():
            try:
                if os.name != "nt":
                    os.chmod(mvnw, 0o755)
            except OSError:
                pass
            return [str(mvnw)]
    # 2. Local tools/ folder or system PATH
    return resolve_mvn()


def _project_cwd_raw(root: Path) -> Path:
    """Find the directory containing pom.xml/build.gradle without calling _project_cwd."""
    p = find_first(root, ["pom.xml"]) or find_first(root, ["build.gradle"]) \
        or find_first(root, ["build.gradle.kts"])
    return p.parent if p else root


def _diagnose_missing(root: Path) -> str:
    """Return a human-readable explanation of why the app cannot be launched."""
    reasons = []
    has_pom = find_first(root, ["pom.xml"]) is not None
    has_gradle = (find_first(root, ["build.gradle"]) or find_first(root, ["build.gradle.kts"])) is not None
    has_mvnw = (
        find_first(root, ["mvnw"]) is not None
        or find_first(root, ["mvnw.cmd"]) is not None
    )
    has_gradlew = (
        find_first(root, ["gradlew"]) is not None
        or find_first(root, ["gradlew.bat"]) is not None
    )
    if not has_pom and not has_gradle:
        reasons.append("no pom.xml or build.gradle found")
    if has_pom and not shutil.which("mvn") and not has_mvnw and not resolve_mvn():
        reasons.append(
            "pom.xml found but 'mvn' not in PATH, no Maven Wrapper (mvnw) and "
            "no local Maven in tools/maven/ — extract Maven zip to tools/maven/"
        )
    if has_gradle and not shutil.which("gradle") and not has_gradlew and not resolve_gradle_system():
        reasons.append(
            "build.gradle found but 'gradle' not in PATH, no Gradle Wrapper (gradlew) and "
            "no local Gradle in tools/gradle/ — extract Gradle zip to tools/gradle/"
        )
    if not shutil.which("java"):
        reasons.append("'java' not found in PATH — JDK required to run the project")
    return "; ".join(reasons) if reasons else "unknown reason"


def _build_command(root: Path) -> Optional[List[str]]:
    cwd_root = _project_cwd_raw(root)
    spring = _looks_like_spring_boot(root)
    mvn = _resolve_mvn(cwd_root) or _resolve_mvn(root)
    has_pom = find_first(root, ["pom.xml"]) is not None
    has_gradle = (find_first(root, ["build.gradle"]) or find_first(root, ["build.gradle.kts"])) is not None
    gradlew = cwd_root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not gradlew.exists():
        gradlew = root / ("gradlew.bat" if os.name == "nt" else "gradlew")

    if spring:
        if has_pom and mvn:
            extra = [_lombok_version_override(root)] if _lombok_version_override(root) else []
            return mvn + ["-q", "spring-boot:run"] + extra
        if gradlew.exists():
            return [str(gradlew), "bootRun", "--no-daemon"]
        if shutil.which("gradle"):
            return ["gradle", "bootRun", "--no-daemon"]
    # Generic Maven or Gradle run
    if has_pom and mvn:
        extra = [_lombok_version_override(root)] if _lombok_version_override(root) else []
        return mvn + ["-q", "exec:java"] + extra
    if gradlew.exists():
        return [str(gradlew), "run", "--no-daemon"]
    if shutil.which("gradle") and has_gradle:
        return ["gradle", "run", "--no-daemon"]
    return None


def _project_cwd(root: Path) -> Path:
    return _project_cwd_raw(root)


H2_VERSION = "2.2.224"

# JVM args injected via .mvn/jvm.config to fix old Lombok on JDK 17+
_JVM_CONFIG_CONTENT = "\n".join([
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
    "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "--add-opens=java.base/java.util=ALL-UNNAMED",
]) + "\n"


def _inject_jvm_config(cwd: Path) -> None:
    """Write .mvn/jvm.config so old Lombok/annotation processors work on JDK 17+."""
    try:
        from ..utils.tools import _java_major_version
        if _java_major_version() < 16:
            return
        mvn_dir = cwd / ".mvn"
        mvn_dir.mkdir(exist_ok=True)
        cfg = mvn_dir / "jvm.config"
        # Only write if not already present (respect project's own config)
        if not cfg.exists():
            cfg.write_text(_JVM_CONFIG_CONTENT, encoding="utf-8")
            log.info("Wrote .mvn/jvm.config for JDK %d Lombok compatibility", _java_major_version())
    except Exception as exc:  # noqa: BLE001
        log.debug("Could not write .mvn/jvm.config: %s", exc)


def _lombok_version_override(root: Path) -> Optional[str]:
    """Return -Dlombok.version=X.Y.Z if project uses old Lombok + JDK 17+."""
    try:
        from ..utils.tools import _java_major_version
        if _java_major_version() < 17:
            return None
        content = _read_build_files(root)
        if "lombok" not in content:
            return None
        # Lombok 1.18.30+ supports JDK 21. Override via Spring Boot's managed property.
        return "-Dlombok.version=1.18.36"
    except Exception:  # noqa: BLE001
        return None


def _ensure_h2_jar(root: Path) -> Optional[Path]:
    """Download H2 jar to local Maven repo and return its path, or None."""
    jar_path = (
        Path.home()
        / ".m2" / "repository" / "com" / "h2database" / "h2" / H2_VERSION
        / f"h2-{H2_VERSION}.jar"
    )
    if jar_path.exists():
        log.info("H2 jar found in local Maven repo: %s", jar_path)
        return jar_path
    mvn = _resolve_mvn(root) or resolve_mvn()
    if not mvn:
        return None
    cwd = _project_cwd_raw(root)
    log.info("Downloading H2 %s into local Maven repo...", H2_VERSION)
    try:
        result = subprocess.run(
            mvn + [
                "dependency:get",
                f"-Dartifact=com.h2database:h2:{H2_VERSION}",
                "-q",
            ],
            cwd=str(cwd),
            capture_output=True,
            timeout=120,
            env=build_env_with_java(),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not download H2: %s", exc)
        return None
    return jar_path if jar_path.exists() else None


def _patch_pom_add_h2(root: Path) -> bool:
    """Add H2 as a runtime dependency in pom.xml (in-clone only) if not present."""
    pom = find_first(root, ["pom.xml"])
    if not pom:
        return False
    try:
        content = pom.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if "com.h2database" in content.lower():
        return False  # H2 already declared
    h2_dep = (
        "\n        <dependency>"
        "\n            <groupId>com.h2database</groupId>"
        "\n            <artifactId>h2</artifactId>"
        "\n            <scope>runtime</scope>"
        "\n        </dependency>"
    )
    # Insert just before the first </dependencies>
    if "</dependencies>" not in content:
        return False
    patched = content.replace("</dependencies>", h2_dep + "\n    </dependencies>", 1)
    try:
        pom.write_text(patched, encoding="utf-8")
        log.info("Patched pom.xml to add H2 runtime dependency (in-clone only)")
        return True
    except OSError as exc:
        log.warning("Could not patch pom.xml: %s", exc)
        return False


@contextmanager
def start_app(root: Path, port: int = 8080, ready_timeout: int = 90) -> Iterator[Optional[str]]:
    """Start app and yield base_url on success, or None on failure."""
    import requests  # local import: only needed for readiness

    cmd = _build_command(root)
    if cmd is None:
        reason = _diagnose_missing(root)
        log.warning("Cannot launch app — skipping dynamic phase. Reason: %s", reason)
        yield None
        return

    cwd = _project_cwd(root)
    _inject_jvm_config(cwd)
    base_url = f"http://localhost:{port}"
    overrides = _build_overrides(root)
    h2_extra = overrides.pop("_H2_EXTRA_CLASSPATH", None)
    # Inject H2 jar into spring-boot:run classpath when needed
    if h2_extra and "spring-boot:run" in " ".join(cmd):
        cmd = cmd + [f"-Dspring-boot.run.additionalClasspathElements={h2_extra}"]
        log.info("Injecting H2 jar into classpath: %s", h2_extra)
    n_overrides = len(overrides)
    if n_overrides:
        log.info("Applying %d Spring Boot env overrides for DB/security", n_overrides)
    log.info("Launching app: %s", " ".join(cmd))
    try:
        env = build_env_with_java()
        env.setdefault("SERVER_PORT", str(port))
        env.update(overrides)
        proc = subprocess.Popen(
            cmd, cwd=str(cwd),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            start_new_session=(os.name != "nt"),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to start app: %s", exc)
        yield None
        return

    ready_url: Optional[str] = None
    crashed = False
    try:
        deadline = time.time() + ready_timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                log.warning(
                    "App crashed on startup (exit code=%s). "
                    "Possible causes: missing dependency, DB unreachable, port conflict.",
                    proc.returncode,
                )
                crashed = True
                break
            for path in READY_PATHS:
                try:
                    r = requests.get(base_url + path, timeout=2)
                    if r.status_code < 500:
                        ready_url = base_url
                        break
                except Exception:  # noqa: BLE001
                    pass
            if ready_url:
                break
            time.sleep(2)
        if not ready_url and not crashed:
            log.warning("App did not respond within %ss (timeout)", ready_timeout)
        yield ready_url
    finally:
        _terminate(proc)


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:  # noqa: BLE001
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass
    try:
        proc.wait(timeout=15)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
