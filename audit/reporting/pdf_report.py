"""PDF report — reportlab; optional, never crashes the pipeline if missing."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..core import get_logger
from ..models import AuditReport

log = get_logger()


def write(report: AuditReport, out_path: Path) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
        )
    except ImportError:
        log.warning("reportlab not installed — skipping PDF")
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    d: Dict[str, Any] = report.to_dict()
    sc = d["score"]

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"ISO 25010 — {d['project']}",
    )
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)

    elements = []
    elements.append(Paragraph(f"Auditoria ISO/IEC 25010 — {d['project']}", h1))
    elements.append(Paragraph(f"Fonte: {d['source']}", small))
    elements.append(Paragraph(
        f"Duração: {d['duration_sec']}s · {d['files_analyzed']} arquivos · "
        f"{d['classes_analyzed']} classes · {d['methods_analyzed']} métodos",
        small,
    ))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Veredito", h2))
    elements.append(Paragraph(f"<b>{sc['status']}</b> — Score geral: {sc['overall']}", body))
    score_table = Table(
        [["Dimensão", "Score"],
         ["Manutenibilidade", sc["maintainability"]],
         ["Confiabilidade", sc["reliability"]],
         ["Performance", sc["performance"]],
         ["Geral", sc["overall"]]],
        colWidths=[80 * mm, 40 * mm],
    )
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c2833")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Alertas", h2))
    if sc["alerts"]:
        for a in sc["alerts"]:
            elements.append(Paragraph(f"• {a}", body))
    else:
        elements.append(Paragraph("Nenhum alerta relevante.", body))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Métricas principais", h2))
    metrics = Table(
        [
            ["Métrica", "Valor", "Classificação"],
            ["Complexidade média", d["complexity"]["average"], d["complexity"]["classification"]],
            ["Complexidade total", d["complexity"]["total"], ""],
            ["CBO médio", d["coupling"]["average"], d["coupling"]["classification"]],
            ["Duplicação (%)", d["duplication"]["percentage"], ""],
            ["Cobertura linhas (%)", d["coverage"]["line_coverage"], d["coverage"]["classification"]],
            ["Latência média (ms)", d["benchmark"]["avg_ms"], ""],
            ["Throughput (req/s)", d["benchmark"]["throughput_rps"], ""],
        ],
        colWidths=[70 * mm, 50 * mm, 50 * mm],
    )
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    elements.append(metrics)
    elements.append(Spacer(1, 10))

    # Top complexity
    elements.append(Paragraph("Top métodos por complexidade", h2))
    top = [["Classe", "Método", "CC", "Local"]]
    for r in d["complexity"]["by_method"][:10]:
        top.append([r["class"], r["method"], r["complexity"], f"{Path(r['file']).name}:{r['line']}"])
    t = Table(top, colWidths=[40 * mm, 50 * mm, 15 * mm, 55 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#566573")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(PageBreak())

    elements.append(Paragraph("Top classes por acoplamento (CBO)", h2))
    top_c = [["Classe", "CBO", "Classificação"]]
    for r in d["coupling"]["by_class"][:15]:
        top_c.append([r["class"], r["cbo"], r["classification"]])
    t2 = Table(top_c, colWidths=[80 * mm, 30 * mm, 40 * mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#566573")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Latência sob carga", h2))
    lat_rows = [["Carga", "Latência média (ms)", "Crescimento (%)"]]
    for lvl in d["latency"]["levels"] or []:
        lat_rows.append([lvl["load"], lvl["avg_ms"], lvl["growth_pct"]])
    if len(lat_rows) == 1:
        lat_rows.append(["—", "Não executado", "—"])
    t3 = Table(lat_rows, colWidths=[40 * mm, 60 * mm, 50 * mm])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#566573")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    elements.append(t3)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Diagnóstico", h2))
    elements.append(Paragraph(
        f"O projeto recebe veredito <b>{sc['status']}</b> com score geral "
        f"{sc['overall']}/100. As dimensões da ISO/IEC 25010 avaliadas indicam "
        f"manutenibilidade {sc['maintainability']}/100, confiabilidade "
        f"{sc['reliability']}/100 e desempenho {sc['performance']}/100. "
        f"Recomenda-se priorizar os itens listados nos alertas acima.",
        body,
    ))

    try:
        doc.build(elements)
    except Exception as exc:  # noqa: BLE001
        log.warning("PDF generation failed: %s", exc)
    return out_path
