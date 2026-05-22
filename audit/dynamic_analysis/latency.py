"""Load / latency analysis at increasing request counts."""
from __future__ import annotations

import statistics
import time
from typing import List

from ..core import get_logger
from ..models import LatencyLevel, LatencyResult

log = get_logger()


def measure(base_url: str, endpoint: str, loads: List[int], timeout: float = 5.0) -> LatencyResult:
    import requests

    if not base_url:
        return LatencyResult(executed=False, notes="No base URL")
    url = base_url.rstrip("/") + (endpoint if endpoint.startswith("/") else "/" + endpoint)
    baseline = 0.0
    levels: List[LatencyLevel] = []
    for load in loads:
        times: List[float] = []
        for _ in range(load):
            t0 = time.perf_counter()
            try:
                r = requests.get(url, timeout=timeout)
                if r.status_code < 500:
                    times.append((time.perf_counter() - t0) * 1000.0)
            except Exception:  # noqa: BLE001
                pass
        if not times:
            levels.append(LatencyLevel(load=load, avg_ms=0.0, growth_pct=0.0))
            continue
        avg = statistics.fmean(times)
        if baseline == 0.0:
            baseline = avg
            growth = 0.0
        else:
            growth = ((avg - baseline) / baseline * 100.0) if baseline else 0.0
        levels.append(LatencyLevel(load=load, avg_ms=round(avg, 2), growth_pct=round(growth, 2)))
        log.info("Load %s -> avg %.2fms (growth %.1f%%)", load, avg, growth)
    return LatencyResult(executed=True, levels=levels)
