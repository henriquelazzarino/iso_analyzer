"""Data models for audit metrics. Pure dataclasses, no external deps."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Parser models
# ---------------------------------------------------------------------------

@dataclass
class MethodInfo:
    name: str
    start_line: int
    end_line: int
    body: str = ""
    cyclomatic_complexity: int = 1


@dataclass
class ClassInfo:
    name: str
    file_path: str
    package: str = ""
    imports: List[str] = field(default_factory=list)
    methods: List[MethodInfo] = field(default_factory=list)
    referenced_types: List[str] = field(default_factory=list)
    line_count: int = 0


# ---------------------------------------------------------------------------
# Static analysis results
# ---------------------------------------------------------------------------

@dataclass
class ComplexityResult:
    total: int = 0
    average: float = 0.0
    by_method: List[Dict[str, Any]] = field(default_factory=list)  # top N
    by_class: List[Dict[str, Any]] = field(default_factory=list)
    critical_files: List[str] = field(default_factory=list)
    classification: str = "Baixa"


@dataclass
class CouplingResult:
    average: float = 0.0
    by_class: List[Dict[str, Any]] = field(default_factory=list)
    critical_classes: List[str] = field(default_factory=list)
    classification: str = "Bom"


@dataclass
class DuplicationResult:
    duplicated_blocks: int = 0
    duplicated_lines: int = 0
    total_lines: int = 0
    percentage: float = 0.0
    samples: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reliability
# ---------------------------------------------------------------------------

@dataclass
class CoverageResult:
    detected_framework: str = "none"  # junit | testng | none
    test_files: int = 0
    executed: bool = False
    success: bool = False
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    classification: str = "N/A"
    notes: str = ""


# ---------------------------------------------------------------------------
# Dynamic analysis
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkSample:
    endpoint: str
    method: str
    status: int
    elapsed_ms: float
    payload_size: int = 0


@dataclass
class BenchmarkResult:
    executed: bool = False
    base_url: str = ""
    endpoints: List[str] = field(default_factory=list)
    samples: List[BenchmarkSample] = field(default_factory=list)
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    stddev_ms: float = 0.0
    throughput_rps: float = 0.0
    notes: str = ""


@dataclass
class LatencyLevel:
    load: int
    avg_ms: float
    growth_pct: float


@dataclass
class LatencyResult:
    executed: bool = False
    levels: List[LatencyLevel] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

@dataclass
class IsoScore:
    maintainability: float = 0.0
    reliability: float = 0.0
    performance: float = 0.0
    overall: float = 0.0
    status: str = "UNKNOWN"  # APPROVED | APPROVED_WITH_RESERVATIONS | FAILED
    alerts: List[str] = field(default_factory=list)


@dataclass
class AuditReport:
    project: str = "unknown"
    source: str = ""
    duration_sec: float = 0.0
    files_analyzed: int = 0
    classes_analyzed: int = 0
    methods_analyzed: int = 0
    complexity: ComplexityResult = field(default_factory=ComplexityResult)
    coupling: CouplingResult = field(default_factory=CouplingResult)
    duplication: DuplicationResult = field(default_factory=DuplicationResult)
    coverage: CoverageResult = field(default_factory=CoverageResult)
    benchmark: BenchmarkResult = field(default_factory=BenchmarkResult)
    latency: LatencyResult = field(default_factory=LatencyResult)
    score: IsoScore = field(default_factory=IsoScore)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
