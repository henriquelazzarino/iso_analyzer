"""HTTP benchmark of detected endpoints."""
from __future__ import annotations

import math
import re
import statistics
import time
from pathlib import Path
from typing import List

from ..core import get_logger
from ..models import BenchmarkResult, BenchmarkSample
from ..utils import safe_read, walk_files

log = get_logger()


# Spring-style endpoint mapping annotations
_MAPPING_RE = re.compile(
    r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)"
    r"\s*\(\s*(?:value\s*=\s*)?\"([^\"]+)\""
)
# Class-level base path
_CLASS_MAPPING_RE = re.compile(
    r"@RequestMapping\s*\(\s*(?:value\s*=\s*)?\"([^\"]+)\""
)


def discover_endpoints(root: Path) -> List[str]:
    seen = set()
    for f in walk_files(root, [".java"]):
        src = safe_read(f)
        if "@" not in src:
            continue
        # Crude: collect base + method-level mappings
        base_match = _CLASS_MAPPING_RE.search(src)
        base = base_match.group(1) if base_match else ""
        for m in _MAPPING_RE.finditer(src):
            ann, path = m.group(1), m.group(2)
            full = (base.rstrip("/") + "/" + path.lstrip("/")) if base else path
            if not full.startswith("/"):
                full = "/" + full
            # Only safe GET-style probes
            if ann in ("GetMapping", "RequestMapping"):
                seen.add(full)
    return sorted(seen)


def benchmark(base_url: str, endpoints: List[str], iterations: int = 20, timeout: float = 5.0) -> BenchmarkResult:
    import requests

    if not base_url:
        return BenchmarkResult(executed=False, notes="No base URL — app not ready")
    if not endpoints:
        endpoints = ["/"]
    samples: List[BenchmarkSample] = []
    t_start = time.time()
    for ep in endpoints:
        # Replace path variables with safe defaults
        safe_ep = re.sub(r"\{[^}]+\}", "1", ep)
        url = base_url.rstrip("/") + safe_ep
        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                r = requests.get(url, timeout=timeout)
                elapsed = (time.perf_counter() - t0) * 1000.0
                samples.append(BenchmarkSample(
                    endpoint=safe_ep,
                    method="GET",
                    status=r.status_code,
                    elapsed_ms=round(elapsed, 2),
                    payload_size=len(r.content or b""),
                ))
            except Exception as exc:  # noqa: BLE001
                log.debug("Benchmark request failed %s: %s", url, exc)
                samples.append(BenchmarkSample(
                    endpoint=safe_ep, method="GET", status=0,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                ))
    total_time = max(time.time() - t_start, 1e-6)
    if not samples:
        return BenchmarkResult(executed=True, base_url=base_url, endpoints=endpoints,
                               notes="No samples collected")
    times = [s.elapsed_ms for s in samples if s.status > 0]
    if not times:
        return BenchmarkResult(executed=True, base_url=base_url, endpoints=endpoints,
                               samples=samples, notes="All requests failed")
    return BenchmarkResult(
        executed=True,
        base_url=base_url,
        endpoints=endpoints,
        samples=samples[:200],
        avg_ms=round(statistics.fmean(times), 2),
        min_ms=round(min(times), 2),
        max_ms=round(max(times), 2),
        stddev_ms=round(statistics.pstdev(times) if len(times) > 1 else 0.0, 2),
        throughput_rps=round(len(times) / total_time, 2),
    )
