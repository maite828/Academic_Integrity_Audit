from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def gauge(label: str, value: int | None, css_class: str) -> str:
    pct = max(0, min(100, int(value or 0)))
    return (
        f'<div class="gauge-card {css_class}">'
        f'<div class="gauge-label">{esc(label)}</div>'
        f'<div class="gauge-wrap" style="--pct:{pct};"><div class="gauge-num">{pct}%</div></div>'
        "</div>"
    )


def write_dashboard(
    path: Path,
    doc_name: str,
    summary: dict[str, Any],
    paragraph_rows: list[dict[str, Any]],
    section_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
) -> None:
    exp = summary.get("experiment") or {}
    top_paragraphs = sorted(paragraph_rows, key=lambda row: (-int(row.get("risk_pct", 0)), -int(row.get("words", 0))))[:12]
    paragraph_html = "\n".join(
        "<tr>"
        f"<td>{row['index']}</td>"
        f"<td>{esc(str(row['section'])[:52])}</td>"
        f"<td>{row['risk_pct']}% {esc(row['risk_label'])}</td>"
        f"<td>{esc(row.get('note') or 'sin alerta fuerte')}</td>"
        f"<td>{esc(str(row['text'])[:260])}</td>"
        "</tr>"
        for row in top_paragraphs
    )
    similarity_html = "\n".join(
        "<tr>"
        f"<td>{row['similarity_pct']}%</td>"
        f"<td>{esc(row['source_doc'])}</td>"
        f"<td>{row['target_paragraph']}</td>"
        f"<td>{row['source_paragraph']}</td>"
        f"<td>{esc(row['target_excerpt'])}</td>"
        "</tr>"
        for row in similarity_rows[:20]
    ) or '<tr><td colspan="5">No se detectaron coincidencias locales relevantes.</td></tr>'

    section_html = "\n".join(
        "<tr>"
        f"<td>{esc(row['section'])}</td>"
        f"<td>{row['paragraphs']}</td>"
        f"<td>{row['words']}</td>"
        f"<td>{row['risk_pct']}%</td>"
        f"<td>{row['quality_pct']}%</td>"
        "</tr>"
        for row in section_rows
    )

    html_doc = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Academic Integrity Audit</title>
  <style>
    :root {{ --bg:#0b1020; --card:#111827; --line:#243041; --text:#e5e7eb; --muted:#94a3b8; --accent:#38bdf8; --good:#22c55e; --bad:#ef4444; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    header {{ padding:28px 34px 18px; border-bottom:1px solid var(--line); background:linear-gradient(135deg,#111827,#0f172a); }}
    h1 {{ margin:0 0 8px; font-size:28px; }}
    main {{ padding:24px 34px 40px; max-width:1240px; margin:0 auto; }}
    .subtitle,.note {{ color:var(--muted); line-height:1.55; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }}
    .card,.gauge-card {{ background:rgba(17,24,39,.86); border:1px solid var(--line); border-radius:16px; padding:18px; box-shadow:0 12px 34px rgba(0,0,0,.18); }}
    .section {{ margin-top:22px; }}
    .kpi {{ font-size:30px; font-weight:760; margin-top:8px; }}
    .kpi-label,.gauge-label {{ color:var(--muted); font-size:13px; }}
    .gauge-wrap {{ width:148px; height:148px; border-radius:50%; margin:8px auto 0; display:grid; place-items:center; background:conic-gradient(var(--accent) calc(var(--pct)*1%),#1f2937 0); position:relative; }}
    .risk .gauge-wrap {{ background:conic-gradient(var(--bad) calc(var(--pct)*1%),#1f2937 0); }}
    .quality .gauge-wrap {{ background:conic-gradient(var(--good) calc(var(--pct)*1%),#1f2937 0); }}
    .gauge-wrap:after {{ content:""; width:110px; height:110px; background:#111827; border-radius:50%; position:absolute; }}
    .gauge-num {{ z-index:1; font-size:30px; font-weight:800; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ border-bottom:1px solid #243041; padding:10px 8px; vertical-align:top; }}
    th {{ color:#cbd5e1; text-align:left; background:#0f172a; }}
    @media(max-width:900px) {{ .grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<header>
  <h1>Academic Integrity Audit</h1>
  <div class="subtitle">Documento: <strong>{esc(doc_name)}</strong>. Auditoria local, explicable y orientada a trazabilidad.</div>
</header>
<main>
  <section class="grid">
    {gauge("Riesgo heuristico", summary.get("ai_style_risk_pct"), "risk")}
    {gauge("Calidad academica", summary.get("academic_quality_pct"), "quality")}
    {gauge("Fiabilidad experimental", summary.get("experiment_reliability_pct"), "quality")}
    <div class="card"><div class="kpi-label">Coincidencias locales</div><div class="kpi">{len(similarity_rows)}</div></div>
  </section>
  <section class="grid section">
    <div class="card"><div class="kpi-label">Palabras</div><div class="kpi">{summary.get("total_words", 0)}</div></div>
    <div class="card"><div class="kpi-label">Parrafos</div><div class="kpi">{summary.get("total_paragraphs", 0)}</div></div>
    <div class="card"><div class="kpi-label">Ejecuciones resueltas</div><div class="kpi">{exp.get("solved", 0)}/{exp.get("rows", 0)}</div></div>
    <div class="card"><div class="kpi-label">Metricas completas</div><div class="kpi">{exp.get("metric_completeness_pct", 0)}%</div></div>
  </section>
  <section class="card section">
    <h2>Secciones</h2>
    <table><thead><tr><th>Seccion</th><th>Parrafos</th><th>Palabras</th><th>Riesgo</th><th>Calidad</th></tr></thead><tbody>{section_html}</tbody></table>
  </section>
  <section class="card section">
    <h2>Parrafos prioritarios</h2>
    <table><thead><tr><th>#</th><th>Seccion</th><th>Riesgo</th><th>Motivo</th><th>Extracto</th></tr></thead><tbody>{paragraph_html}</tbody></table>
  </section>
  <section class="card section">
    <h2>Similitud local</h2>
    <p class="note">Coincidencias internas o contra corpus local. No implica plagio confirmado; indica coincidencia textual que requiere revision.</p>
    <table><thead><tr><th>Similitud</th><th>Fuente</th><th>Parrafo objetivo</th><th>Parrafo fuente</th><th>Extracto objetivo</th></tr></thead><tbody>{similarity_html}</tbody></table>
  </section>
</main>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


def write_markdown(
    path: Path,
    summary: dict[str, Any],
    section_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
) -> None:
    lines = [
        "# Academic Integrity Audit",
        "",
        f"- Riesgo heuristico: **{summary.get('ai_style_risk_pct', 0)}%**",
        f"- Calidad academica: **{summary.get('academic_quality_pct', 0)}%**",
        f"- Fiabilidad experimental: **{summary.get('experiment_reliability_pct', 'n/a')}%**",
        f"- Coincidencias locales: **{len(similarity_rows)}**",
        "",
        "## Secciones",
        "",
        "| Seccion | Parrafos | Palabras | Riesgo | Calidad |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in section_rows:
        lines.append(
            f"| {str(row['section'])[:70]} | {row['paragraphs']} | {row['words']} | {row['risk_pct']}% | {row['quality_pct']}% |"
        )
    lines.extend(["", "## Similitud local", ""])
    if similarity_rows:
        for row in similarity_rows[:12]:
            lines.append(
                f"- {row['similarity_pct']}% con `{row['source_doc']}` "
                f"(objetivo parrafo {row['target_paragraph']}, fuente parrafo {row['source_paragraph']})."
            )
    else:
        lines.append("- No se detectaron coincidencias locales relevantes.")
    path.write_text("\n".join(lines), encoding="utf-8")

