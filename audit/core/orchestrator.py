"""Top-level audit orchestrator.

Coordinates every module behind a single fault-tolerant `run()` function.
Each phase is wrapped in try/except so one failure cannot kill the audit.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .logger import get_logger
from ..models import AuditReport
from ..utils import is_git_url, clone, project_name_from_url, walk_files, ensure_dir
from ..parsers import parse_java_source
from ..static_analysis import complexity, coupling, duplication
from ..reliability import detect_tests, collect_coverage, classify_coverage
from ..executors import detect_build_system, run_tests, start_app
from ..dynamic_analysis import discover_endpoints, benchmark, measure_latency
from ..reporting import scorer, json_report, html_report, pdf_report

log = get_logger()


@dataclass
class AuditOptions:
    source: str
    output_dir: Path
    timeout: int = 300
    skip_dynamic: bool = False
    skip_tests: bool = False
    loads: List[int] = field(default_factory=lambda: [100, 500, 1000, 5000])
    clone_root: Optional[Path] = None


def run(opts: AuditOptions) -> AuditReport:
    started = time.time()
    report = AuditReport(source=opts.source)

    # ---- Phase 1: acquire ------------------------------------------------
    project_root = _acquire(opts, report)
    if project_root is None:
        report.duration_sec = round(time.time() - started, 2)
        report.score = scorer.score(report)
        _emit(report, opts)
        return report
    report.project = project_root.name

    # ---- Phase 2: parse --------------------------------------------------
    java_files = list(walk_files(project_root, [".java"]))
    classes = []
    for f in java_files:
        try:
            classes.extend(parse_java_source(f))
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"parse failed: {f}: {exc}")
    report.files_analyzed = len(java_files)
    report.classes_analyzed = len(classes)
    report.methods_analyzed = sum(len(c.methods) for c in classes)
    log.info("Parsed %d files / %d classes / %d methods",
             report.files_analyzed, report.classes_analyzed, report.methods_analyzed)

    # ---- Phase 3: static analysis ---------------------------------------
    _safe(lambda: setattr(report, "complexity", complexity.analyze(classes)),
          report, "complexity")
    _safe(lambda: setattr(report, "coupling", coupling.analyze(classes)),
          report, "coupling")
    _safe(lambda: setattr(report, "duplication", duplication.analyze(java_files)),
          report, "duplication")

    # ---- Phase 4: tests + coverage --------------------------------------
    if not opts.skip_tests:
        _run_tests_phase(project_root, report, opts.timeout)
    else:
        log.info("Skipping tests phase (--no-tests)")

    # ---- Phase 5: dynamic ------------------------------------------------
    if not opts.skip_dynamic:
        _run_dynamic_phase(project_root, report, opts)
    else:
        log.info("Skipping dynamic phase (--no-dynamic)")

    # ---- Phase 6: score + emit -------------------------------------------
    report.duration_sec = round(time.time() - started, 2)
    report.score = scorer.score(report)
    _emit(report, opts)
    return report


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

def _acquire(opts: AuditOptions, report: AuditReport) -> Optional[Path]:
    src = opts.source.strip()
    try:
        if is_git_url(src):
            clone_root = opts.clone_root or (opts.output_dir / ".tmp_clones")
            path = clone(src, clone_root, timeout=opts.timeout)
            if path is None:
                report.errors.append("git clone failed")
            return path
        path = Path(src).expanduser().resolve()
        if not path.exists():
            report.errors.append(f"local path does not exist: {path}")
            return None
        if not path.is_dir():
            report.errors.append(f"path is not a directory: {path}")
            return None
        return path
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"acquire failed: {exc}")
        return None


def _run_tests_phase(root: Path, report: AuditReport, timeout: int) -> None:
    try:
        framework, count = detect_tests(root)
        report.coverage.detected_framework = framework
        report.coverage.test_files = count
        log.info("Detected test framework: %s (%d files)", framework, count)
        if framework == "none":
            report.coverage.notes = "No JUnit/TestNG tests found."
            return
        if detect_build_system(root) == "none":
            report.coverage.notes = "No Maven/Gradle build present — cannot run tests."
            return
        success, output, _ = run_tests(root, timeout=timeout)
        report.coverage.executed = True
        report.coverage.success = success
        if not success:
            tail = (output or "")[-400:]
            report.coverage.notes = f"Tests failed/build error. Tail: {tail}"
        line, branch, src = collect_coverage(root)
        report.coverage.line_coverage = round(line, 2)
        report.coverage.branch_coverage = round(branch, 2)
        report.coverage.classification = classify_coverage(line)
        if src:
            report.coverage.notes = (report.coverage.notes + f" Source: {src}").strip()
        elif success:
            report.coverage.notes = "Tests ran but no JaCoCo XML found."
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"tests phase failed: {exc}")
        report.coverage.notes = f"Exception: {exc}"


def _run_dynamic_phase(root: Path, report: AuditReport, opts: AuditOptions) -> None:
    try:
        endpoints = discover_endpoints(root)
        log.info("Discovered %d candidate endpoints", len(endpoints))
        with start_app(root, ready_timeout=min(opts.timeout, 120)) as base_url:
            if not base_url:
                report.benchmark.notes = "App did not start — dynamic phase skipped."
                return
            report.benchmark = benchmark(base_url, endpoints or ["/"], iterations=20)
            ep_for_load = endpoints[0] if endpoints else "/"
            report.latency = measure_latency(base_url, ep_for_load, opts.loads)
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"dynamic phase failed: {exc}")
        report.benchmark.notes = f"Exception: {exc}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(action, report: AuditReport, label: str) -> None:
    try:
        action()
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"{label} failed: {exc}")
        log.exception("%s failed", label)


def _emit(report: AuditReport, opts: AuditOptions) -> None:
    out = ensure_dir(opts.output_dir)
    try:
        json_report.write(report, out / "metrics.json")
    except Exception as exc:  # noqa: BLE001
        log.error("JSON report failed: %s", exc)
    try:
        html_report.write(report, out / "report.html")
    except Exception as exc:  # noqa: BLE001
        log.error("HTML report failed: %s", exc)
    try:
        pdf_report.write(report, out / "report.pdf")
    except Exception as exc:  # noqa: BLE001
        log.error("PDF report failed: %s", exc)
    log.info("Reports written to %s", out)
