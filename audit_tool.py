"""ISO/IEC 25010 Audit Tool — CLI entrypoint.

Usage:
    python audit_tool.py analyze <git-url|local-path> [options]

Options:
    --output DIR        Output directory (default: ./audit-output)
    --no-dynamic        Skip benchmark/latency phase
    --no-tests          Skip tests/coverage phase
    --timeout SEC       Per-phase timeout (default: 300)
    --load LIST         Override loads (comma-separated, e.g. 100,500,1000)
    --verbose           Verbose logging
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audit.core import setup_logger, AuditOptions, run
from audit.utils.tools import tools_status, detect_java_home

_MAVEN_VERSION = "3.9.16"
_MAVEN_ZIP_URL = (
    f"https://dlcdn.apache.org/maven/maven-3/{_MAVEN_VERSION}/binaries/"
    f"apache-maven-{_MAVEN_VERSION}-bin.zip"
)
_MAVEN_TAR_URL = (
    f"https://dlcdn.apache.org/maven/maven-3/{_MAVEN_VERSION}/binaries/"
    f"apache-maven-{_MAVEN_VERSION}-bin.tar.gz"
)


def _cmd_setup() -> int:
    import platform, shutil, urllib.request, zipfile, tarfile, tempfile, os

    root = Path(__file__).resolve().parent
    maven_dest = root / "tools" / "maven"
    expected_bin = maven_dest / f"apache-maven-{_MAVEN_VERSION}" / "bin"

    print()
    print("=== ISO Analyzer — Setup ===")
    print()

    # ── Java ──────────────────────────────────────────────────────────────────
    jh = detect_java_home()
    if jh:
        print(f"  [OK] Java: {jh}")
    else:
        print("  [!!] Java nao encontrado. Instale o JDK 11+ e adicione ao PATH.")
        print("       Download: https://adoptium.net/")

    # ── Git ───────────────────────────────────────────────────────────────────
    git = shutil.which("git")
    if git:
        print(f"  [OK] git: {git}")
    else:
        print("  [!!] git nao encontrado. Instale o Git e adicione ao PATH.")
        print("       Download: https://git-scm.com/downloads")

    # ── Maven ─────────────────────────────────────────────────────────────────
    mvn_sys = shutil.which("mvn") or shutil.which("mvn.cmd")
    if mvn_sys:
        print(f"  [OK] Maven (sistema): {mvn_sys}")
        print()
        print("  Ambiente pronto. Rode: python audit_tool.py analyze <url-ou-pasta>")
        print()
        return 0

    if (expected_bin / ("mvn.cmd" if platform.system() == "Windows" else "mvn")).exists():
        print(f"  [OK] Maven (local): {expected_bin}")
        print()
        print("  Ambiente pronto. Rode: python audit_tool.py analyze <url-ou-pasta>")
        print()
        return 0

    print(f"  [ ] Maven nao encontrado — baixando {_MAVEN_VERSION}...")
    maven_dest.mkdir(parents=True, exist_ok=True)

    is_windows = platform.system() == "Windows"
    url = _MAVEN_ZIP_URL if is_windows else _MAVEN_TAR_URL
    suffix = ".zip" if is_windows else ".tar.gz"

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        print(f"      Baixando de {url} ...")
        urllib.request.urlretrieve(url, tmp_path)
        print(f"      Extraindo para {maven_dest} ...")

        if is_windows:
            with zipfile.ZipFile(tmp_path) as zf:
                zf.extractall(maven_dest)
        else:
            with tarfile.open(tmp_path, "r:gz") as tf:
                tf.extractall(maven_dest)

        os.unlink(tmp_path)

        # Ensure mvn is executable on Linux/macOS
        if not is_windows:
            mvn_bin = expected_bin / "mvn"
            mvn_bin.chmod(mvn_bin.stat().st_mode | 0o111)

        print(f"  [OK] Maven instalado em: {expected_bin}")

    except Exception as exc:  # noqa: BLE001
        print(f"  [!!] Falha ao baixar Maven: {exc}")
        print(f"       Baixe manualmente de https://maven.apache.org/download.cgi")
        print(f"       e extraia em: {maven_dest}")
        return 1

    # ── Python deps ───────────────────────────────────────────────────────────
    try:
        import requests  # noqa: F401
        import reportlab  # noqa: F401
        print("  [OK] Dependencias Python: requests, reportlab")
    except ImportError:
        print("  [ ] Dependencias Python faltando. Rode: pip install -r requirements.txt")

    print()
    print("  Ambiente pronto. Rode: python audit_tool.py analyze <url-ou-pasta>")
    print()
    return 0




def _parse_loads(text: str):
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out or [100, 500, 1000, 5000]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit-tool",
        description="ISO/IEC 25010 audit for Java repositories",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    analyze = sub.add_parser("analyze", help="Audit a Java repository (git URL or local path)")
    analyze.add_argument("source", help="Git URL or local directory path")
    analyze.add_argument("--output", default="./audit-output", help="Output directory")
    analyze.add_argument("--no-dynamic", action="store_true")
    analyze.add_argument("--no-tests", action="store_true")
    analyze.add_argument("--timeout", type=int, default=300)
    analyze.add_argument("--load", type=str, default="100,500,1000,5000")
    analyze.add_argument("--verbose", action="store_true")

    sub.add_parser("tools", help="Show detected build tools (mvn, gradle, java)")
    sub.add_parser("setup", help="Download Maven locally and verify all dependencies")

    args = parser.parse_args(argv)
    if args.cmd == "tools":
        status = tools_status()
        print("\n=== Build Tools Status ===")
        labels = {
            "java_path":    "java     (runtime)",
            "javac_path":   "javac    (compiler)",
            "mvn_path":     "mvn      (PATH)",
            "mvn_local":    "mvn      (tools/maven/)",
            "gradle_path":  "gradle   (PATH)",
            "gradle_local": "gradle   (tools/gradle/)",
            "git_path":     "git      (PATH)",
        }
        for key, label in labels.items():
            val = status[key]
            mark = "OK  " if val else "----"
            detail = f"  → {val}" if isinstance(val, str) and val else ""
            print(f"  [{mark}] {label}{detail}")
        print()
        print(f"  To use local Maven: extract apache-maven-*.zip to tools/maven/")
        print(f"  To use local Gradle: extract gradle-*.zip to tools/gradle/")
        jh = detect_java_home()
        print(f"\n  JAVA_HOME detected: {jh or 'NOT FOUND'}")
        print()
        return 0

    if args.cmd == "setup":
        return _cmd_setup()

    if args.cmd != "analyze":
        parser.print_help()
        return 2

    out_dir = Path(args.output).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    log = setup_logger(verbose=args.verbose, log_file=out_dir / "audit.log")
    log.info("ISO/IEC 25010 Audit Tool starting…")
    log.info("Source: %s", args.source)
    log.info("Output: %s", out_dir)

    opts = AuditOptions(
        source=args.source,
        output_dir=out_dir,
        timeout=args.timeout,
        skip_dynamic=args.no_dynamic,
        skip_tests=args.no_tests,
        loads=_parse_loads(args.load),
    )
    try:
        report = run(opts)
    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        return 130
    except Exception as exc:  # noqa: BLE001
        log.exception("Unhandled error: %s", exc)
        return 1

    sc = report.score
    print()
    print("================ AUDIT SUMMARY ================")
    print(f" Project       : {report.project}")
    print(f" Verdict       : {sc.status}")
    print(f" Overall score : {sc.overall}/100")
    print(f" Maintainability: {sc.maintainability}   Reliability: {sc.reliability}   Performance: {sc.performance}")
    print(f" Files/Classes/Methods: {report.files_analyzed}/{report.classes_analyzed}/{report.methods_analyzed}")
    print(f" Reports       : {out_dir}")
    print("================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
