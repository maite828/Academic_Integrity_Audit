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


def has_model_scores(review: dict[str, Any]) -> bool:
    return all(
        review.get(key) is not None
        for key in ("ai_usage_risk_pct", "plagiarism_risk_pct", "quality_score_pct")
    )


def optional_pct(value: Any) -> str:
    return "n/a" if value is None else f"{value}%"


def source_role_label(value: Any) -> str:
    return {
        "student_response": "respuesta",
        "assignment_prompt": "enunciado",
        "metadata": "metadatos",
    }.get(str(value), str(value))


def write_dashboard(
    path: Path,
    doc_name: str,
    summary: dict[str, Any],
    paragraph_rows: list[dict[str, Any]],
    section_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
) -> None:
    exp = summary.get("experiment") or {}
    ai_review = summary.get("ai_model_review") or {}
    has_ai_review = (
        summary.get("audit_mode") == "ai_plus_heuristics"
        and ai_review.get("available")
        and has_model_scores(ai_review)
    )
    ai_risk_label = "Riesgo IA combinado" if has_ai_review else "Riesgo estilo IA"
    originality_label = "Riesgo originalidad" if has_ai_review else "Riesgo similitud local"
    quality_label = "Calidad integral" if has_ai_review else "Calidad heuristica"
    explanations = summary.get("metric_explanations") or {}
    rubric = summary.get("academic_rubric") or []
    separated = summary.get("separated_reading") or []
    originality_scope = summary.get("originality_scope") or {}
    source_roles = summary.get("source_role_summary") or {}
    role_labels = {
        "student_response": "Respuesta evaluable",
        "assignment_prompt": "Posible enunciado",
        "metadata": "Portada/metadatos",
    }
    source_scope = (
        "Se puntuó solo la respuesta evaluable detectada."
        if summary.get("scoring_exclusions_active")
        else "Se puntuó todo el texto extraído porque no había una separación fiable."
    )
    source_role_html = "\n".join(
        "<tr>"
        f"<td>{esc(role_labels.get(role, role))}</td>"
        f"<td>{values.get('paragraphs', 0)}</td>"
        f"<td>{values.get('words', 0)}</td>"
        "</tr>"
        for role, values in source_roles.items()
    )
    top_paragraphs = sorted(paragraph_rows, key=lambda row: (-int(row.get("risk_pct", 0)), -int(row.get("words", 0))))[:12]
    paragraph_html = "\n".join(
        "<tr>"
        f"<td>{row['index']}</td>"
        f"<td>{esc(str(row['section'])[:52])}</td>"
        f"<td>{esc(source_role_label(row.get('source_role')))}</td>"
        f"<td>{row['risk_pct']}% {esc(row['risk_label'])}</td>"
        f"<td>{esc(row.get('note') or 'sin alerta fuerte')}</td>"
        f"<td>{esc(str(row['text'])[:260])}</td>"
        "</tr>"
        for row in top_paragraphs
    )
    similarity_html = "\n".join(
        "<tr>"
        f"<td>{row['similarity_pct']}%</td>"
        f"<td>{esc(row.get('source_kind', 'local'))}</td>"
        f"<td>{esc(row['source_doc'])}</td>"
        f"<td>{row['target_paragraph']}</td>"
        f"<td>{row['source_paragraph']}</td>"
        f"<td>{esc(row['target_excerpt'])}</td>"
        "</tr>"
        for row in similarity_rows[:20]
    ) or '<tr><td colspan="6">No se detectaron coincidencias locales relevantes.</td></tr>'
    ignored_reasons_html = "\n".join(
        "<tr>"
        f"<td>{esc(reason)}</td>"
        f"<td>{count}</td>"
        "</tr>"
        for reason, count in (originality_scope.get("ignored_reasons") or {}).items()
    ) or '<tr><td colspan="2">No se ignoraron parrafos por reglas de comparabilidad.</td></tr>'
    corpus_docs_html = "".join(
        f"<li>{esc(item)}</li>" for item in (originality_scope.get("corpus_document_names") or [])
    ) or "<li>No se aporto corpus local externo.</li>"
    unreadable_docs_html = "".join(
        f"<li>{esc(item)}</li>" for item in (originality_scope.get("unreadable_corpus_documents") or [])
    ) or "<li>Sin documentos rechazados.</li>"
    originality_scope_html = f"""
  <section class="card section">
    <h2>Alcance de originalidad local</h2>
    <p class="note">{esc(originality_scope.get('method', 'Comparacion local de parrafos.'))}</p>
    <div class="grid">
      <div class="card"><div class="kpi-label">Umbral local</div><div class="kpi">{originality_scope.get('threshold_pct', 0)}%</div></div>
      <div class="card"><div class="kpi-label">Parrafos comparables</div><div class="kpi">{originality_scope.get('comparable_paragraphs', 0)}</div></div>
      <div class="card"><div class="kpi-label">Parrafos ignorados</div><div class="kpi">{originality_scope.get('ignored_paragraphs', 0)}</div></div>
      <div class="card"><div class="kpi-label">Maxima similitud vista</div><div class="kpi">{originality_scope.get('max_observed_similarity_pct', 0)}%</div></div>
    </div>
    <p class="note">{esc(originality_scope.get('limitation', 'No consulta fuentes externas.'))}</p>
    <table><thead><tr><th>Motivo de descarte</th><th>Parrafos</th></tr></thead><tbody>{ignored_reasons_html}</tbody></table>
    <h3>Corpus local comparado</h3>
    <ul>{corpus_docs_html}</ul>
    <h3>Corpus no legible</h3>
    <ul>{unreadable_docs_html}</ul>
  </section>
"""
    ai_reasons = "".join(f"<li>{esc(item)}</li>" for item in ai_review.get("ai_risk_reasons", []))
    plagiarism_reasons = "".join(f"<li>{esc(item)}</li>" for item in ai_review.get("plagiarism_risk_reasons", []))
    recommendations = "".join(f"<li>{esc(item)}</li>" for item in ai_review.get("quality_recommendations", []))
    confidence_reasons = "".join(f"<li>{esc(item)}</li>" for item in ai_review.get("confidence_reasons", []))
    confidence_warnings = "".join(f"<li>{esc(item)}</li>" for item in ai_review.get("confidence_warnings", []))
    defense_questions = summary.get("defense_questions") or ai_review.get("teacher_questions", [])
    questions = "".join(f"<li>{esc(item)}</li>" for item in defense_questions)
    if has_ai_review:
        ai_html = f"""
  <section class="card section">
    <h2>Revision con IA local</h2>
    <p class="note">Modelo local: <strong>{esc(ai_review.get('model'))}</strong>. Estas cifras son estimaciones explicables, no una prueba definitiva de uso de IA ni de plagio.</p>
    <div class="grid">
      <div class="card"><div class="kpi-label">Riesgo uso IA</div><div class="kpi">{esc(ai_review.get('ai_usage_risk_pct'))}%</div></div>
      <div class="card"><div class="kpi-label">Riesgo plagio/originalidad</div><div class="kpi">{esc(ai_review.get('plagiarism_risk_pct'))}%</div></div>
      <div class="card"><div class="kpi-label">Calidad segun modelo</div><div class="kpi">{esc(ai_review.get('quality_score_pct'))}%</div></div>
      <div class="card"><div class="kpi-label">Veredicto</div><p>{esc(ai_review.get('overall_verdict') or 'Sin veredicto especifico del modelo.')}</p></div>
    </div>
    <div class="grid section">
      <div class="card"><div class="kpi-label">Confianza salida modelo</div><div class="kpi">{esc(ai_review.get('confidence_pct', 0))}%</div><p>{esc(ai_review.get('confidence_label', 'n/a'))}</p></div>
      <div class="card"><div class="kpi-label">Razones de confianza</div><ul>{confidence_reasons or "<li>Sin razones destacadas.</li>"}</ul></div>
      <div class="card"><div class="kpi-label">Advertencias de confianza</div><ul>{confidence_warnings or "<li>Sin advertencias.</li>"}</ul></div>
      <div class="card"><div class="kpi-label">Reintento JSON</div><p>{esc('si' if ai_review.get('retry_used') else 'no')}</p></div>
    </div>
    <h3>Motivos de riesgo IA</h3><ul>{ai_reasons or "<li>Sin motivos destacados.</li>"}</ul>
    <h3>Motivos de originalidad/plagio</h3><ul>{plagiarism_reasons or "<li>Sin motivos destacados.</li>"}</ul>
    <h3>Recomendaciones de calidad</h3><ul>{recommendations or "<li>Sin recomendaciones destacadas.</li>"}</ul>
    <h3>Preguntas de defensa</h3><ul>{questions or "<li>Sin preguntas destacadas.</li>"}</ul>
  </section>
"""
    else:
        ai_html = f"""
  <section class="card section">
    <h2>Revision con IA local</h2>
    <p class="note">No se ejecuto el modelo local. El informe esta en modo heuristico y usa solo senales documentales, similitud local y trazabilidad experimental disponible.</p>
    <p class="note">Motivo: {esc(summary.get('ai_unavailable_reason') or ai_review.get('error') or 'modelo no disponible')}</p>
  </section>
"""

    section_html = "\n".join(
        "<tr>"
        f"<td>{esc(row['section'])}</td>"
        f"<td>{row['paragraphs']}</td>"
        f"<td>{row.get('evaluable_paragraphs', row['paragraphs'])}</td>"
        f"<td>{row.get('excluded_paragraphs', 0)}</td>"
        f"<td>{row['words']}</td>"
        f"<td>{row['risk_pct']}%</td>"
        f"<td>{row['quality_pct']}%</td>"
        "</tr>"
        for row in section_rows
    )
    rubric_html = "\n".join(
        "<tr>"
        f"<td>{esc(row.get('criterion'))}</td>"
        f"<td>{esc(row.get('label'))}</td>"
        f"<td>{row.get('score_pct')}%</td>"
        f"<td>{esc('; '.join(row.get('evidence') or []))}</td>"
        f"<td>{esc('; '.join(row.get('warnings') or []) or 'sin advertencias')}</td>"
        "</tr>"
        for row in rubric
    )
    separated_html = "\n".join(
        '<div class="card">'
        f'<div class="kpi-label">{esc(row.get("area"))}</div>'
        f'<div class="kpi">{row.get("score_pct")}%</div>'
        f'<p><strong>{esc(row.get("status"))}</strong></p>'
        f'<p class="note">{esc(row.get("interpretation"))}</p>'
        "</div>"
        for row in separated
    )
    explanation_html = "\n".join(
        f"<li><strong>{esc(label)}</strong>: {esc(explanations.get(key, 'sin detalle'))}</li>"
        for key, label in [
            ("combined_ai_usage_risk_pct", ai_risk_label),
            ("combined_originality_risk_pct", originality_label),
            ("combined_quality_score_pct", quality_label),
        ]
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
    {gauge(ai_risk_label, summary.get("combined_ai_usage_risk_pct"), "risk")}
    {gauge(originality_label, summary.get("combined_originality_risk_pct"), "risk")}
    {gauge(quality_label, summary.get("combined_quality_score_pct"), "quality")}
    {gauge("Fiabilidad experimental", summary.get("experiment_reliability_pct"), "quality")}
  </section>
  <section class="card section">
    <h2>Como se interpretan las puntuaciones</h2>
    <ul>{explanation_html}</ul>
    <p class="note">Estas metricas orientan la revision humana. No prueban por si solas uso de IA, plagio ni autoria.</p>
  </section>
  <section class="card section">
    <h2>Contenido usado para puntuar</h2>
    <p class="note">{esc(source_scope)}</p>
    <table><thead><tr><th>Tipo</th><th>Parrafos</th><th>Palabras</th></tr></thead><tbody>{source_role_html}</tbody></table>
  </section>
  <section class="section">
    <h2>Lectura separada del informe</h2>
    <div class="grid">{separated_html}</div>
  </section>
  <section class="grid section">
    <div class="card"><div class="kpi-label">Riesgo heuristico</div><div class="kpi">{summary.get("ai_style_risk_pct", 0)}%</div></div>
    <div class="card"><div class="kpi-label">Calidad heuristica</div><div class="kpi">{summary.get("academic_quality_pct", 0)}%</div></div>
    <div class="card"><div class="kpi-label">Modo auditoria</div><div class="kpi">{esc("IA local" if summary.get("audit_mode") == "ai_plus_heuristics" else "Heuristica")}</div></div>
    <div class="card"><div class="kpi-label">Coincidencias locales</div><div class="kpi">{len(similarity_rows)}</div></div>
  </section>
  <section class="grid section">
    <div class="card"><div class="kpi-label">Palabras</div><div class="kpi">{summary.get("total_words", 0)}</div></div>
    <div class="card"><div class="kpi-label">Parrafos</div><div class="kpi">{summary.get("total_paragraphs", 0)}</div></div>
    <div class="card"><div class="kpi-label">Ejecuciones resueltas</div><div class="kpi">{exp.get("solved", 0)}/{exp.get("rows", 0)}</div></div>
    <div class="card"><div class="kpi-label">Metricas completas</div><div class="kpi">{exp.get("metric_completeness_pct", 0)}%</div></div>
  </section>
  <section class="card section">
    <h2>Rubrica academica</h2>
    <p class="note">Resumen por criterios derivados de senales observables del documento.</p>
    <table><thead><tr><th>Criterio</th><th>Estado</th><th>Puntuacion</th><th>Evidencia usada</th><th>Advertencias</th></tr></thead><tbody>{rubric_html}</tbody></table>
  </section>
  <section class="card section">
    <h2>Secciones</h2>
    <table><thead><tr><th>Seccion</th><th>Parrafos</th><th>Evaluables</th><th>Excluidos</th><th>Palabras</th><th>Riesgo</th><th>Calidad</th></tr></thead><tbody>{section_html}</tbody></table>
  </section>
  {ai_html}
  <section class="card section">
    <h2>Parrafos prioritarios</h2>
    <table><thead><tr><th>#</th><th>Seccion</th><th>Tipo</th><th>Riesgo</th><th>Motivo</th><th>Extracto</th></tr></thead><tbody>{paragraph_html}</tbody></table>
  </section>
  {originality_scope_html}
  <section class="card section">
    <h2>Similitud local</h2>
    <p class="note">Coincidencias internas o contra corpus local. No implica plagio confirmado; indica coincidencia textual que requiere revision.</p>
    <table><thead><tr><th>Similitud</th><th>Tipo</th><th>Fuente</th><th>Parrafo objetivo</th><th>Parrafo fuente</th><th>Extracto objetivo</th></tr></thead><tbody>{similarity_html}</tbody></table>
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
    has_ai_review = summary.get("audit_mode") == "ai_plus_heuristics" and (summary.get("ai_model_review") or {}).get("available")
    ai_risk_label = "Riesgo IA combinado" if has_ai_review else "Riesgo estilo IA"
    originality_label = "Riesgo originalidad combinado" if has_ai_review else "Riesgo similitud local"
    quality_label = "Calidad integral" if has_ai_review else "Calidad heuristica"
    originality_scope = summary.get("originality_scope") or {}
    lines = [
        "# Academic Integrity Audit",
        "",
        f"- {ai_risk_label}: **{summary.get('combined_ai_usage_risk_pct', 0)}%**",
        f"- {originality_label}: **{summary.get('combined_originality_risk_pct', 0)}%**",
        f"- {quality_label}: **{summary.get('combined_quality_score_pct', 0)}%**",
        f"- Modo de auditoria: **{'IA local + heuristicas' if summary.get('audit_mode') == 'ai_plus_heuristics' else 'solo heuristicas'}**",
        f"- Texto puntuado: **{summary.get('scored_words', summary.get('total_words', 0))} de {summary.get('total_words', 0)} palabras**",
        "",
        "## Interpretacion de puntuaciones",
        "",
        f"- {ai_risk_label}: {summary.get('metric_explanations', {}).get('combined_ai_usage_risk_pct', 'sin detalle')}",
        f"- {originality_label}: {summary.get('metric_explanations', {}).get('combined_originality_risk_pct', 'sin detalle')}",
        f"- {quality_label}: {summary.get('metric_explanations', {}).get('combined_quality_score_pct', 'sin detalle')}",
        "",
        "## Lectura separada del informe",
        "",
        "| Area | Estado | Puntuacion | Interpretacion |",
        "|---|---|---:|---|",
    ]
    for item in summary.get("separated_reading") or []:
        lines.append(
            f"| {item.get('area')} | {item.get('status')} | {item.get('score_pct')}% | "
            f"{item.get('interpretation')} |"
        )
    lines.extend(
        [
            "",
            "## Contenido usado para puntuar",
            "",
            (
                "- Se puntuo solo la respuesta evaluable detectada."
                if summary.get("scoring_exclusions_active")
                else "- Se puntuo todo el texto extraido porque no habia una separacion fiable."
            ),
            "",
            "| Tipo | Parrafos | Palabras |",
            "|---|---:|---:|",
        ]
    )
    role_labels = {
        "student_response": "Respuesta evaluable",
        "assignment_prompt": "Posible enunciado",
        "metadata": "Portada/metadatos",
    }
    for role, values in (summary.get("source_role_summary") or {}).items():
        lines.append(
            f"| {role_labels.get(role, role)} | {values.get('paragraphs', 0)} | {values.get('words', 0)} |"
        )
    lines.extend(
        [
            "",
        "## Rubrica academica",
        "",
        "| Criterio | Estado | Puntuacion | Evidencia usada | Advertencias |",
        "|---|---|---:|---|---|",
        ]
    )
    for item in summary.get("academic_rubric") or []:
        lines.append(
            f"| {item.get('criterion')} | {item.get('label')} | {item.get('score_pct')}% | "
            f"{'; '.join(item.get('evidence') or [])} | "
            f"{'; '.join(item.get('warnings') or []) or 'sin advertencias'} |"
        )
    lines.extend(
        [
            "",
            "## Resumen heuristico",
            "",
        ]
    )
    lines.extend(
        [
        f"- Riesgo heuristico: **{summary.get('ai_style_risk_pct', 0)}%**",
        f"- Calidad academica: **{summary.get('academic_quality_pct', 0)}%**",
        f"- Fiabilidad experimental: **{optional_pct(summary.get('experiment_reliability_pct'))}**",
        f"- Coincidencias locales: **{len(similarity_rows)}**",
        "",
        "## Secciones",
        "",
        "| Seccion | Parrafos | Evaluables | Excluidos | Palabras | Riesgo | Calidad |",
        "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in section_rows:
        lines.append(
            f"| {str(row['section'])[:70]} | {row['paragraphs']} | "
            f"{row.get('evaluable_paragraphs', row['paragraphs'])} | {row.get('excluded_paragraphs', 0)} | "
            f"{row['words']} | {row['risk_pct']}% | {row['quality_pct']}% |"
        )
    lines.extend(
        [
            "",
            "## Alcance de originalidad local",
            "",
            f"- Metodo: {originality_scope.get('method', 'Comparacion local de parrafos.')}",
            f"- Umbral local: **{originality_scope.get('threshold_pct', 0)}%**",
            f"- Parrafos comparables: **{originality_scope.get('comparable_paragraphs', 0)}**",
            f"- Parrafos ignorados: **{originality_scope.get('ignored_paragraphs', 0)}**",
            f"- Maxima similitud observada: **{originality_scope.get('max_observed_similarity_pct', 0)}%**",
            f"- Corpus local aportado: **{'si' if originality_scope.get('corpus_enabled') else 'no'}**",
            f"- Limitacion: {originality_scope.get('limitation', 'No consulta fuentes externas.')}",
            "",
            "### Documentos del corpus comparados",
            "",
        ]
    )
    corpus_docs = originality_scope.get("corpus_document_names") or []
    if corpus_docs:
        lines.extend(f"- {item}" for item in corpus_docs)
    else:
        lines.append("- No se aporto corpus local externo.")
    unreadable_docs = originality_scope.get("unreadable_corpus_documents") or []
    if unreadable_docs:
        lines.extend(["", "### Documentos del corpus no legibles", ""])
        lines.extend(f"- {item}" for item in unreadable_docs)
    lines.extend(
        [
            "",
            "| Motivo de descarte | Parrafos |",
            "|---|---:|",
        ]
    )
    ignored_reasons = originality_scope.get("ignored_reasons") or {}
    if ignored_reasons:
        for reason, count in ignored_reasons.items():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| No se ignoraron parrafos por reglas de comparabilidad | 0 |")
    lines.extend(["", "## Similitud local", ""])
    if similarity_rows:
        for row in similarity_rows[:12]:
            lines.append(
                f"- {row['similarity_pct']}% ({row.get('source_kind', 'local')}) con `{row['source_doc']}` "
                f"(objetivo parrafo {row['target_paragraph']}, fuente parrafo {row['source_paragraph']})."
            )
    else:
        lines.append("- No se detectaron coincidencias locales relevantes.")
    lines.extend(["", "## Preguntas de defensa", ""])
    for question in summary.get("defense_questions") or []:
        lines.append(f"- {question}")
    ai_review = summary.get("ai_model_review") or {}
    lines.extend(["", "## Revision con IA local", ""])
    if ai_review.get("available"):
        lines.extend(
            [
                f"- Modelo: **{ai_review.get('model')}**",
                f"- Confianza de la salida del modelo: **{ai_review.get('confidence_pct', 0)}% ({ai_review.get('confidence_label', 'n/a')})**",
                f"- Riesgo estimado de uso de IA: **{ai_review.get('ai_usage_risk_pct')}%**",
                f"- Riesgo estimado de plagio/originalidad: **{ai_review.get('plagiarism_risk_pct')}%**",
                f"- Calidad estimada por modelo: **{ai_review.get('quality_score_pct')}%**",
                f"- Veredicto: {ai_review.get('overall_verdict') or 'Sin veredicto especifico del modelo.'}",
                "",
                "### Confianza del modelo",
                "",
                *(f"- {item}" for item in (ai_review.get("confidence_reasons") or ["Sin razones destacadas."])),
                "",
                "### Advertencias de confianza",
                "",
                *(f"- {item}" for item in (ai_review.get("confidence_warnings") or ["Sin advertencias."])),
                "",
                "Nota: estas cifras son estimaciones explicables; no prueban por si solas uso de IA ni plagio.",
            ]
        )
    else:
        lines.extend(
            [
                "- No se ejecuto el modelo local.",
                f"- Motivo: {summary.get('ai_unavailable_reason') or ai_review.get('error') or 'modelo no disponible'}",
                "- El informe queda en modo heuristico.",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def teacher_action(summary: dict[str, Any]) -> tuple[str, str]:
    ai_risk = int(summary.get("combined_ai_usage_risk_pct") or 0)
    originality_risk = int(summary.get("combined_originality_risk_pct") or 0)
    quality = int(summary.get("combined_quality_score_pct") or 0)
    if originality_risk >= 60:
        return (
            "Revisar originalidad antes de calificar",
            "Hay riesgo alto de originalidad. Contraste las coincidencias y pida defensa focalizada antes de cerrar la evaluación.",
        )
    if ai_risk >= 60:
        return (
            "Pedir defensa focalizada",
            "El estilo presenta señales fuertes compatibles con uso intensivo de IA. No es prueba; conviene verificar comprensión con preguntas concretas.",
        )
    if quality < 60:
        return (
            "Pedir mejora académica",
            "La prioridad no es sancionar, sino aclarar estructura, evidencia o trazabilidad antes de valorar el trabajo como sólido.",
        )
    if ai_risk >= 30 or originality_risk >= 30:
        return (
            "Calificar con revisión dirigida",
            "El trabajo puede revisarse con foco en las alertas concretas y las preguntas de defensa.",
        )
    return (
        "Calificar con revisión ordinaria",
        "No aparecen señales locales fuertes. Mantenga la revisión humana habitual y use las preguntas como verificación ligera.",
    )


def warning_lines(summary: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in summary.get("academic_rubric") or []:
        for warning in item.get("warnings") or []:
            lines.append(f"- {item.get('criterion')}: {warning}")
    if not lines:
        lines.append("- No hay advertencias destacadas en la rúbrica.")
    return lines


def write_teacher_report(
    path: Path,
    doc_name: str,
    summary: dict[str, Any],
    paragraph_rows: list[dict[str, Any]],
    similarity_rows: list[dict[str, Any]],
) -> None:
    action, action_reason = teacher_action(summary)
    originality_scope = summary.get("originality_scope") or {}
    ai_review = summary.get("ai_model_review") or {}
    top_paragraphs = sorted(
        paragraph_rows,
        key=lambda row: (-int(row.get("risk_pct", 0)), -int(row.get("words", 0))),
    )[:5]

    lines = [
        "# Informe para profesor",
        "",
        f"- Documento: **{doc_name}**",
        f"- Acción sugerida: **{action}**",
        f"- Motivo: {action_reason}",
        "",
        "## Lectura rápida",
        "",
        f"- Riesgo estilo IA: **{summary.get('combined_ai_usage_risk_pct', 0)}%**",
        f"- Riesgo originalidad: **{summary.get('combined_originality_risk_pct', 0)}%**",
        f"- Calidad integral: **{summary.get('combined_quality_score_pct', 0)}%**",
        f"- Modo: **{'IA local + heurísticas' if summary.get('audit_mode') == 'ai_plus_heuristics' else 'solo heurísticas'}**",
        f"- Modelo local: **{summary.get('ai_model_used') or 'sin modelo local'}**",
        f"- Confianza salida modelo: **{ai_review.get('confidence_pct', 0)}% ({ai_review.get('confidence_label', 'n/a')})**",
        f"- Texto puntuado: **{summary.get('scored_words', summary.get('total_words', 0))} de {summary.get('total_words', 0)} palabras**",
        "",
        "## Qué revisar primero",
        "",
        *warning_lines(summary),
        *(
            [f"- Modelo local: {warning}" for warning in ai_review.get("confidence_warnings", [])]
            if ai_review.get("available")
            else ["- Modelo local: no hubo una salida de IA válida."]
        ),
        "",
        "## Originalidad local",
        "",
        f"- Coincidencias locales relevantes: **{len(similarity_rows)}**",
        f"- Máxima similitud observada: **{originality_scope.get('max_observed_similarity_pct', 0)}%**",
        f"- Párrafos comparables: **{originality_scope.get('comparable_paragraphs', 0)}**",
        f"- Párrafos ignorados por brevedad/plantilla: **{originality_scope.get('ignored_paragraphs', 0)}**",
        f"- Corpus local externo aportado: **{'sí' if originality_scope.get('corpus_enabled') else 'no'}**",
        f"- Documentos del corpus comparados: **{originality_scope.get('corpus_documents', 0)}**",
        "",
        "## Preguntas de defensa",
        "",
    ]
    questions = summary.get("defense_questions") or ai_review.get("teacher_questions") or []
    if questions:
        lines.extend(f"- {question}" for question in questions[:8])
    else:
        lines.append("- No se generaron preguntas de defensa concretas.")

    lines.extend(["", "## Fragmentos útiles para revisión", ""])
    for row in top_paragraphs:
        note = row.get("note") or "sin alerta fuerte"
        excerpt = str(row.get("text") or "")[:220]
        lines.append(
            f"- Párrafo {row.get('index')} ({row.get('section')}): "
            f"{row.get('risk_pct')}% {row.get('risk_label')}. {note}. Extracto: {excerpt}"
        )

    lines.extend(
        [
            "",
            "## Límites de uso",
            "",
            "- Este informe no prueba plagio, uso de IA ni autoría.",
            "- La originalidad local no consulta internet ni bases externas.",
            "- La autoría solo puede confirmarse con defensa, proceso verificable o evidencias externas.",
            "- Use el resultado para orientar revisión humana, no como sanción automática.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
