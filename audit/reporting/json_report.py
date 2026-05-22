"""JSON report writer."""
from __future__ import annotations

import json
from pathlib import Path

from ..models import AuditReport


def write(report: AuditReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path
