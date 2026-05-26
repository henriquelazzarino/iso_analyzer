"""HTML report — single-file dashboard using stdlib only."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List

from ..models import AuditReport


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _status_color(status: str) -> str:
    s = (status or "").upper()
    if "NÃO CONFORME" in s:
        return "#c0392b"
    if "RESSALV" in s:
        return "#d68910"
    if "CONFORME" in s:
        return "#1e8449"
    return "#566573"


def _bar(value: float, color: str = "#2e86c1") -> str:
    v = max(0.0, min(100.0, float(value)))
    return (
        f'<div class="bar"><div class="fill" style="width:{v:.1f}%;'
        f'background:{color}"></div><span>{v:.1f}</span></div>'
    )


def _rows_methods(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return '<tr><td colspan="5">Sem dados.</td></tr>'
    out = []
    for r in rows[:15]:
        out.append(
            f"<tr><td>{_e(r['class'])}</td><td>{_e(r['method'])}</td>"
            f"<td>{_e(r['complexity'])}</td><td>{_e(r['classification'])}</td>"
            f"<td><code>{_e(r['file'])}:{_e(r['line'])}</code></td></tr>"
        )
    return "\n".join(out)


def _rows_classes(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return '<tr><td colspan="4">Sem dados.</td></tr>'
    out = []
    for r in rows[:15]:
        deps = ", ".join(r.get("dependencies", [])[:8])
        out.append(
            f"<tr><td>{_e(r['class'])}</td><td>{_e(r['cbo'])}</td>"
            f"<td>{_e(r['classification'])}</td><td><small>{_e(deps)}</small></td></tr>"
        )
    return "\n".join(out)


def _rows_dup(samples: List[Dict[str, Any]]) -> str:
    if not samples:
        return '<tr><td colspan="3">Nenhuma duplicação relevante.</td></tr>'
    out = []
    for s in samples[:10]:
        locs = "<br>".join(f"{_e(l['file'])}:{_e(l['line'])}" for l in s["locations"])
        snippet = _e(s["sample"])[:400]
        out.append(
            f"<tr><td>{_e(s['occurrences'])}</td>"
            f"<td><small>{locs}</small></td>"
            f"<td><pre>{snippet}</pre></td></tr>"
        )
    return "\n".join(out)


def _rows_latency(levels: List[Any]) -> str:
    if not levels:
        return '<tr><td colspan="3">Não executado.</td></tr>'
    out = []
    for lvl in levels:
        out.append(
            f"<tr><td>{_e(lvl['load'])}</td>"
            f"<td>{_e(lvl['avg_ms'])} ms</td>"
            f"<td>{_e(lvl['growth_pct'])}%</td></tr>"
        )
    return "\n".join(out)


def _alerts_html(alerts: List[str]) -> str:
    if not alerts:
        return '<p class="ok">Nenhum alerta relevante.</p>'
    items = "\n".join(f"<li>{_e(a)}</li>" for a in alerts)
    return f"<ul class='alerts'>{items}</ul>"


def write(report: AuditReport, out_path: Path) -> Path:
    d = report.to_dict()
    sc = d["score"]
    status_color = _status_color(sc["status"])
    html_doc = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Auditoria ISO/IEC 25010 — {_e(d['project'])}</title>
<style>
  :root {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, sans-serif; color: #1c2833; }}
  body {{ margin: 0; padding: 0; background: #f4f6f7; }}
  header {{ background: #1c2833; color: white; padding: 24px 40px; }}
  header h1 {{ margin: 0; font-size: 22px; }}
  header .source {{ opacity: 0.7; font-size: 13px; margin-top: 4px; }}
  main {{ max-width: 1100px; margin: 24px auto; padding: 0 24px; }}
  section {{ background: white; border-radius: 8px; padding: 20px 24px;
            margin-bottom: 18px; box-shadow: 0 1px 2px rgba(0,0,0,.05); }}
  section h2 {{ margin: 0 0 12px 0; font-size: 16px; border-bottom: 1px solid #ecf0f1;
                padding-bottom: 6px; color: #2c3e50; }}
  .verdict {{ display: inline-block; padding: 10px 18px; border-radius: 6px;
              color: white; font-weight: 700; background: {status_color}; }}
  .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
  .kpi {{ background: #fbfcfc; border: 1px solid #ecf0f1; border-radius: 6px;
          padding: 14px; text-align: center; }}
  .kpi .label {{ font-size: 12px; color: #7f8c8d; text-transform: uppercase; }}
  .kpi .value {{ font-size: 26px; font-weight: 700; color: #2c3e50; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 7px 9px; border-bottom: 1px solid #ecf0f1; text-align: left; }}
  th {{ background: #f8f9f9; }}
  pre {{ margin: 0; background: #f4f6f7; padding: 8px; border-radius: 4px;
         font-size: 11px; max-height: 120px; overflow: auto; }}
  .bar {{ position: relative; background: #ecf0f1; border-radius: 4px; height: 18px;
          overflow: hidden; }}
  .bar .fill {{ height: 100%; transition: width .4s; }}
  .bar span {{ position: absolute; right: 8px; top: 0; font-size: 11px; line-height: 18px;
               color: #1c2833; font-weight: 600; }}
  ul.alerts li {{ margin: 4px 0; }}
  .ok {{ color: #1e8449; font-weight: 600; }}
  code {{ background: #f4f6f7; padding: 1px 4px; border-radius: 3px; font-size: 12px; }}
  footer {{ text-align: center; color: #95a5a6; font-size: 12px; padding: 18px; }}
</style>
</head>
<body>
<header>
  <h1>Auditoria ISO/IEC 25010 — {_e(d['project'])}</h1>
  <div class="source">Fonte: {_e(d['source'])} · Duração: {_e(d['duration_sec'])}s
       · {_e(d['files_analyzed'])} arquivos · {_e(d['classes_analyzed'])} classes
       · {_e(d['methods_analyzed'])} métodos</div>
</header>
<main>

<section>
  <h2>Veredito</h2>
  <p><span class="verdict">{_e(sc['status'])}</span></p>
  <div class="grid">
    <div class="kpi"><div class="label">Geral</div><div class="value">{sc['overall']}</div>{_bar(sc['overall'], status_color)}</div>
    <div class="kpi"><div class="label">Manutenibilidade</div><div class="value">{sc['maintainability']}</div>{_bar(sc['maintainability'])}</div>
    <div class="kpi"><div class="label">Confiabilidade</div><div class="value">{sc['reliability']}</div>{_bar(sc['reliability'], '#7d3c98')}</div>
  </div>
  <div class="grid" style="margin-top:12px;grid-template-columns:repeat(1,1fr)">
    <div class="kpi"><div class="label">Performance</div><div class="value">{sc['performance']}</div>{_bar(sc['performance'], '#117864')}</div>
  </div>
</section>

<section>
  <h2>Alertas</h2>
  {_alerts_html(sc['alerts'])}
</section>

<section>
  <h2>Manutenibilidade — Complexidade Ciclomática</h2>
  <p>Média do projeto: <b>{_e(d['complexity']['average'])}</b>
     ({_e(d['complexity']['classification'])}) · Total: {_e(d['complexity']['total'])}</p>
  <table>
    <thead><tr><th>Classe</th><th>Método</th><th>CC</th><th>Classe</th><th>Local</th></tr></thead>
    <tbody>{_rows_methods(d['complexity']['by_method'])}</tbody>
  </table>
</section>

<section>
  <h2>Manutenibilidade — Acoplamento (CBO)</h2>
  <p>CBO médio: <b>{_e(d['coupling']['average'])}</b> ({_e(d['coupling']['classification'])})</p>
  <table>
    <thead><tr><th>Classe</th><th>CBO</th><th>Classe</th><th>Dependências (parcial)</th></tr></thead>
    <tbody>{_rows_classes(d['coupling']['by_class'])}</tbody>
  </table>
</section>

<section>
  <h2>Manutenibilidade — Duplicação</h2>
  <p>{_e(d['duplication']['duplicated_blocks'])} blocos duplicados ·
     {_e(d['duplication']['duplicated_lines'])} linhas ·
     {_e(d['duplication']['percentage'])}% do código.</p>
  <table>
    <thead><tr><th>Ocorrências</th><th>Locais</th><th>Trecho</th></tr></thead>
    <tbody>{_rows_dup(d['duplication']['samples'])}</tbody>
  </table>
</section>

<section>
  <h2>Confiabilidade — Cobertura de Testes</h2>
  <p>Framework: <b>{_e(d['coverage']['detected_framework'])}</b> ·
     Arquivos de teste: {_e(d['coverage']['test_files'])} ·
     Execução: {"OK" if d['coverage']['success'] else "Falhou/Pulada"}<br>
     Cobertura de linhas: <b>{_e(d['coverage']['line_coverage'])}%</b>
     ({_e(d['coverage']['classification'])}) ·
     Cobertura de branches: {_e(d['coverage']['branch_coverage'])}%</p>
  <p><small>{_e(d['coverage']['notes'])}</small></p>
</section>

<section>
  <h2>Performance — Benchmark</h2>
  <p>Endpoints detectados: {_e(len(d['benchmark']['endpoints']))} ·
     Avg: <b>{_e(d['benchmark']['avg_ms'])}ms</b> ·
     Min: {_e(d['benchmark']['min_ms'])}ms ·
     Max: {_e(d['benchmark']['max_ms'])}ms ·
     Throughput: {_e(d['benchmark']['throughput_rps'])} req/s</p>
  <p><small>{_e(d['benchmark']['notes'])}</small></p>
</section>

<section>
  <h2>Performance — Latência sob carga</h2>
  <table>
    <thead><tr><th>Carga</th><th>Latência média</th><th>Crescimento</th></tr></thead>
    <tbody>{_rows_latency(d['latency']['levels'])}</tbody>
  </table>
</section>

<section>
  <h2>Erros não-fatais durante a auditoria</h2>
  {"<ul>" + "".join(f"<li><code>{_e(e)}</code></li>" for e in d['errors']) + "</ul>"
   if d['errors'] else "<p class='ok'>Nenhum.</p>"}
</section>

</main>
<footer>Gerado por ISO/IEC 25010 Audit Tool · v1.0</footer>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path
