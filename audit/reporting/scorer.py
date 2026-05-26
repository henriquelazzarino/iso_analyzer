"""ISO/IEC 25010 scoring.

We compute three sub-scores (0..100), an overall score, and a status verdict.

Heuristics
----------
Maintainability: weighted from complexity (avg cc), coupling (avg CBO), duplication%.
Reliability: dominated by line coverage; penalized when no tests were detected.
Performance: based on benchmark avg latency and latency growth at higher loads.

These are intentionally simple and explainable — the goal is a defensible
parecer técnico, not a black-box rating.
"""
from __future__ import annotations

from typing import List

from ..models import AuditReport, IsoScore


def _maintainability(report: AuditReport) -> float:
    cc = report.complexity.average or 0.0
    cbo = report.coupling.average or 0.0
    dup = report.duplication.percentage or 0.0
    # Linear penalties (clamped)
    cc_score = max(0.0, 100.0 - max(0.0, cc - 5.0) * 6.0)        # >5 starts hurting
    cbo_score = max(0.0, 100.0 - max(0.0, cbo - 5.0) * 5.0)      # >5 starts hurting
    dup_score = max(0.0, 100.0 - dup * 2.0)                      # 1% dup = -2 pts
    return round((cc_score * 0.4) + (cbo_score * 0.35) + (dup_score * 0.25), 2)


def _reliability(report: AuditReport) -> float:
    cov = report.coverage
    if cov.detected_framework == "none":
        # No tests at all → strong penalty but not zero (project may be early-stage)
        return 15.0
    if not cov.executed:
        # Tests detected but couldn't run → partial credit
        return 35.0
    line = cov.line_coverage or 0.0
    branch = cov.branch_coverage or 0.0
    return round((line * 0.7) + (branch * 0.3), 2)


def _performance(report: AuditReport) -> float:
    bench = report.benchmark
    lat = report.latency
    if not bench.executed:
        return 50.0  # neutral if not measurable
    # Lower is better — 50ms baseline = 100, 1000ms = 0
    avg = bench.avg_ms or 0.0
    base = max(0.0, 100.0 - max(0.0, avg - 50.0) * 0.1)
    growth_penalty = 0.0
    if lat.executed and lat.levels:
        max_growth = max((lvl.growth_pct for lvl in lat.levels), default=0.0)
        growth_penalty = min(40.0, max(0.0, max_growth) * 0.4)
    return round(max(0.0, base - growth_penalty), 2)


def _verdict(overall: float) -> str:
    if overall >= 80:
        return "CONFORME"
    if overall >= 60:
        return "CONFORME COM RESSALVAS"
    return "NÃO CONFORME"


def _alerts(report: AuditReport) -> List[str]:
    out: List[str] = []
    if report.complexity.average > 10:
        out.append(f"Complexidade ciclomática média alta ({report.complexity.average}).")
    for row in report.complexity.by_method[:3]:
        if row["complexity"] > 20:
            out.append(f"Método {row['class']}.{row['method']} com complexidade crítica ({row['complexity']}).")
    if report.coupling.average > 10:
        out.append(f"Acoplamento médio elevado (CBO={report.coupling.average}).")
    for c in report.coupling.critical_classes[:3]:
        out.append(f"Classe {c} apresenta CBO crítico.")
    if report.duplication.percentage > 10:
        out.append(f"Duplicação alta: {report.duplication.percentage}% das linhas.")
    if report.coverage.detected_framework == "none":
        out.append("Nenhum framework de testes detectado (JUnit/TestNG).")
    elif report.coverage.executed and report.coverage.line_coverage < 40:
        out.append(f"Cobertura crítica: {report.coverage.line_coverage:.1f}% de linhas.")
    if report.benchmark.executed and report.benchmark.avg_ms > 500:
        out.append(f"Latência média alta: {report.benchmark.avg_ms}ms.")
    if report.latency.executed and report.latency.levels:
        worst = max(report.latency.levels, key=lambda l: l.growth_pct)
        if worst.growth_pct > 50:
            out.append(
                f"Degradação severa sob carga: +{worst.growth_pct}% em {worst.load} requisições."
            )
    return out


def score(report: AuditReport) -> IsoScore:
    m = _maintainability(report)
    r = _reliability(report)
    p = _performance(report)
    overall = round((m * 0.45) + (r * 0.35) + (p * 0.20), 2)
    return IsoScore(
        maintainability=m,
        reliability=r,
        performance=p,
        overall=overall,
        status=_verdict(overall),
        alerts=_alerts(report),
    )
