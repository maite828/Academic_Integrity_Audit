from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from academic_audit.document.docx_reader import read_document_paragraphs
from academic_audit.document.style_audit import (
    audit_paragraphs,
    audit_sections,
    is_scored_source_role,
    paragraph_rows,
    section_rows,
    summarize_document,
)
from academic_audit.ai.ollama_review import run_ollama_review
from academic_audit.experiment.results_audit import load_results
from academic_audit.originality.local_similarity import find_local_matches_with_scope, similarity_rows
from academic_audit.reports.dashboard import write_dashboard, write_markdown, write_teacher_report
from academic_audit.reports.writers import write_csv, write_json


DEFAULT_AI_MODEL = "llama3.1"


def _pct(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return 0


def _count(value: Any) -> int:
    try:
        return max(0, int(round(float(value))))
    except Exception:
        return 0


def _local_similarity_risk(sim_rows: list[dict[str, Any]]) -> int:
    values = [_pct(row.get("similarity_pct")) for row in sim_rows]
    return max(values, default=0)


def _has_model_scores(review: dict[str, Any]) -> bool:
    return all(
        review.get(key) is not None
        for key in ("ai_usage_risk_pct", "plagiarism_risk_pct", "quality_score_pct")
    )


def _score_label(score: int) -> str:
    if score >= 80:
        return "solido"
    if score >= 60:
        return "revisable"
    return "debil"


def _apply_cap(score: int, cap: int, warnings: list[str], reason: str) -> int:
    if score > cap:
        warnings.append(reason)
        return cap
    return score


def _rubric_item(
    criterion: str,
    score: int,
    evidence: list[str],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "criterion": criterion,
        "score_pct": _pct(score),
        "label": _score_label(score),
        "evidence": evidence,
        "warnings": warnings or [],
    }


def _add_metric_explanations(summary: dict[str, Any], sim_rows: list[dict[str, Any]]) -> None:
    review = summary.get("ai_model_review") or {}
    local_similarity_risk = _local_similarity_risk(sim_rows)
    originality_scope = summary.get("originality_scope") or {}
    originality_scope_text = (
        f"{originality_scope.get('comparable_paragraphs', 0)} parrafos comparables; "
        f"{originality_scope.get('ignored_paragraphs', 0)} ignorados por brevedad/plantilla."
    )
    if summary.get("audit_mode") == "ai_plus_heuristics" and _has_model_scores(review):
        summary["metric_explanations"] = {
            "combined_ai_usage_risk_pct": (
                f"45% heuristica documental ({_pct(summary.get('ai_style_risk_pct'))}%) + "
                f"55% modelo local ({_pct(review.get('ai_usage_risk_pct'))}%)."
            ),
            "combined_originality_risk_pct": (
                f"Maximo entre similitud local ({local_similarity_risk}%) y "
                f"riesgo de originalidad del modelo ({_pct(review.get('plagiarism_risk_pct'))}%). "
                f"Alcance local: {originality_scope_text}"
            ),
            "combined_quality_score_pct": (
                f"60% calidad heuristica ({_pct(summary.get('academic_quality_pct'))}%) + "
                f"40% calidad estimada por modelo ({_pct(review.get('quality_score_pct'))}%)."
            ),
        }
    else:
        summary["metric_explanations"] = {
            "combined_ai_usage_risk_pct": (
                f"Solo heuristica documental ({_pct(summary.get('ai_style_risk_pct'))}%). "
                "No hubo revision de modelo local valida."
            ),
            "combined_originality_risk_pct": f"Solo similitud local ({local_similarity_risk}%). Alcance local: {originality_scope_text}",
            "combined_quality_score_pct": (
                f"Solo calidad heuristica ({_pct(summary.get('academic_quality_pct'))}%). "
                "No hubo estimacion de calidad por modelo."
            ),
        }


def _add_academic_rubric(summary: dict[str, Any], sim_rows: list[dict[str, Any]]) -> None:
    table_count = _count(summary.get("table_count"))
    figure_count = _count(summary.get("figure_count"))
    visual_count = table_count + figure_count
    evidence_density = _pct(summary.get("evidence_density_pct"))
    first_person = _count(summary.get("first_person_total"))
    trace_terms = summary.get("trace_terms_found") or []
    metric_terms = summary.get("metric_terms_found") or []
    reference_terms = summary.get("reference_terms_found") or []
    ai_disclosure = summary.get("ai_disclosure_terms_found") or []
    code_terms = summary.get("code_terms_found") or []
    citation_like_count = _count(summary.get("citation_like_count"))
    cliche_total = _count(summary.get("cliche_total"))
    very_long = _count(summary.get("very_long_paragraphs"))
    scored_paragraphs = _count(summary.get("scored_paragraphs", summary.get("total_paragraphs", 0)))
    scored_words = _count(summary.get("scored_words", summary.get("total_words", 0)))
    local_similarity_risk = _local_similarity_risk(sim_rows)
    originality_scope = summary.get("originality_scope") or {}

    structure_warnings: list[str] = []
    structure_score = _pct(
        min(scored_words / 2500, 1) * 32
        + min(scored_paragraphs / 35, 1) * 28
        + min(visual_count / 8, 1) * 22
        + min(len(metric_terms) + len(trace_terms), 5) * 2
        + (8 if summary.get("scoring_exclusions_active") else 12)
    )
    if scored_words < 1200:
        structure_score = _apply_cap(structure_score, 72, structure_warnings, "Texto evaluable breve para una valoracion estructural alta.")
    if visual_count == 0:
        structure_score = _apply_cap(structure_score, 84, structure_warnings, "No se detectaron tablas ni figuras que sostengan cobertura visual.")

    evidence_warnings: list[str] = []
    evidence_score = _pct(
        22
        + evidence_density * 0.42
        + min(len(metric_terms), 5) * 4
        + min(len(trace_terms), 4) * 5
        + min(len(reference_terms) + citation_like_count, 4) * 3
        + min(len(code_terms), 4) * 2
    )
    if not trace_terms:
        evidence_score = _apply_cap(evidence_score, 84, evidence_warnings, "No se detectaron trazas reproducibles claras.")
    if not reference_terms and citation_like_count == 0:
        evidence_score = _apply_cap(evidence_score, 82, evidence_warnings, "No se detectaron referencias o citas reconocibles.")

    originality_warnings: list[str] = []
    max_observed = _pct(originality_scope.get("max_observed_similarity_pct"))
    comparable = _count(originality_scope.get("comparable_paragraphs"))
    originality_score = _pct(100 - local_similarity_risk - min(12, round(max_observed * 0.15)))
    if not originality_scope.get("corpus_enabled"):
        originality_score = _apply_cap(
            originality_score,
            92,
            originality_warnings,
            "Originalidad calculada solo con repeticiones internas; no hay corpus local externo.",
        )
    if comparable < 5:
        originality_score = _apply_cap(
            originality_score,
            75,
            originality_warnings,
            "Hay pocos parrafos comparables para una lectura local fuerte.",
        )

    style_warnings: list[str] = []
    style_score = _pct(100 - summary.get("ai_style_risk_pct", 0) - min(12, cliche_total * 1.5) - very_long * 4)
    if cliche_total >= 6:
        style_warnings.append("Conectores o formulaciones previsibles repetidas.")
    if very_long:
        style_warnings.append("Hay parrafos excesivamente largos que reducen claridad.")

    authorship_warnings: list[str] = []
    authorship_score = _pct(
        35
        + min(first_person, 5) * 5
        + min(len(ai_disclosure), 1) * 10
        + min(len(trace_terms), 4) * 5
        + min(len(reference_terms) + citation_like_count, 4) * 4
        + min(len(summary.get("defense_focus") or []), 6) * 3
    )
    if not reference_terms and citation_like_count == 0:
        authorship_score = _apply_cap(authorship_score, 82, authorship_warnings, "Faltan referencias o citas para reforzar autoria academica.")
    if not trace_terms:
        authorship_score = _apply_cap(authorship_score, 78, authorship_warnings, "Faltan trazas reproducibles que ayuden a defender el proceso.")
    authorship_score = _apply_cap(
        authorship_score,
        95,
        authorship_warnings,
        "La autoria no se puede confirmar sin defensa oral o evidencias externas adicionales.",
    )
    if not ai_disclosure:
        authorship_warnings.append("No se detecto declaracion de uso o no uso de IA.")

    rubric = [
        _rubric_item(
            "Estructura y cobertura",
            structure_score,
            [
                f"{summary.get('total_paragraphs', 0)} unidades evaluadas",
                f"{scored_words} palabras puntuadas",
                f"{table_count} tablas detectadas",
                f"{figure_count} figuras detectadas",
            ],
            structure_warnings,
        ),
        _rubric_item(
            "Evidencia y trazabilidad",
            evidence_score,
            [
                f"Densidad de evidencia: {evidence_density}%",
                f"Terminos metricos: {', '.join(metric_terms[:6]) or 'no destacados'}",
                f"Trazas: {', '.join(trace_terms[:6]) or 'no destacadas'}",
                f"Referencias/citas: {len(reference_terms) + citation_like_count}",
            ],
            evidence_warnings,
        ),
        _rubric_item(
            "Originalidad local",
            originality_score,
            [
                f"Coincidencias locales relevantes: {len(sim_rows)}",
                f"Mayor coincidencia relevante: {local_similarity_risk}%",
                f"Maxima similitud observada: {max_observed}%",
                f"Corpus local externo: {'si' if originality_scope.get('corpus_enabled') else 'no'}",
            ],
            originality_warnings,
        ),
        _rubric_item(
            "Claridad y estilo academico",
            style_score,
            [
                f"Riesgo heuristico de estilo: {summary.get('ai_style_risk_pct', 0)}%",
                f"Cliches detectados: {cliche_total}",
                f"Parrafos muy largos: {very_long}",
            ],
            style_warnings,
        ),
        _rubric_item(
            "Autoria y defensa",
            authorship_score,
            [
                f"Primera persona academica: {first_person}",
                f"Declaracion IA: {'si' if ai_disclosure else 'no detectada'}",
                f"Referencias/fuentes: {', '.join(reference_terms[:5]) or 'no destacadas'}",
                f"Focos de defensa: {len(summary.get('defense_focus') or [])}",
            ],
            authorship_warnings,
        ),
    ]
    summary["academic_rubric"] = rubric
    summary["academic_rubric_score_pct"] = round(sum(item["score_pct"] for item in rubric) / len(rubric))


def _rubric_score(summary: dict[str, Any], criterion: str, fallback: int) -> int:
    for item in summary.get("academic_rubric") or []:
        if item.get("criterion") == criterion:
            return _pct(item.get("score_pct"))
    return fallback


def _risk_label(score: int) -> str:
    if score >= 60:
        return "alto"
    if score >= 30:
        return "revisar"
    return "bajo"


def _add_separated_reading(summary: dict[str, Any], sim_rows: list[dict[str, Any]]) -> None:
    quality = _pct(summary.get("combined_quality_score_pct"))
    ai_risk = _pct(summary.get("combined_ai_usage_risk_pct"))
    originality_risk = _pct(summary.get("combined_originality_risk_pct"))
    authorship = _rubric_score(summary, "Autoria y defensa", 0)

    summary["separated_reading"] = [
        {
            "area": "Calidad academica",
            "score_pct": quality,
            "status": _score_label(quality),
            "interpretation": "Evalua estructura, evidencia, claridad y solidez academica; no equivale a sospecha.",
        },
        {
            "area": "Riesgo de estilo IA",
            "score_pct": ai_risk,
            "status": _risk_label(ai_risk),
            "interpretation": "Senala estilo compatible con uso intensivo de IA; no prueba autoria artificial.",
        },
        {
            "area": "Originalidad",
            "score_pct": originality_risk,
            "status": _risk_label(originality_risk),
            "interpretation": "Combina similitud local comparable y estimacion prudente del modelo; no sustituye busqueda externa.",
        },
        {
            "area": "Autoria y defensa",
            "score_pct": authorship,
            "status": _score_label(authorship),
            "interpretation": "Resume evidencias que ayudan a defender comprension, decisiones y trazabilidad del trabajo.",
        },
    ]


def _is_generic_question(question: str) -> bool:
    lower = question.lower()
    generic = [
        "explique su trabajo",
        "como realizo el trabajo",
        "qué aprendió",
        "que aprendio",
        "puede explicar",
    ]
    return len(question.split()) < 7 or any(item in lower for item in generic)


def _fallback_teacher_questions(summary: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    for focus in summary.get("defense_focus") or []:
        lower = focus.lower()
        if lower.startswith("tabla"):
            label = re.match(r"(?i)tabla\s+\d+", focus)
            questions.append(
                f"¿Qué resultado resume {label.group(0).capitalize() if label else 'esta tabla'} "
                "y cómo lo obtuvo a partir del análisis?"
            )
        elif lower.startswith("figura"):
            label = re.match(r"(?i)figura\s+\d+", focus)
            questions.append(
                f"¿Qué muestra {label.group(0).capitalize() if label else 'esta figura'} "
                "y qué decisión metodológica justifica?"
            )
        elif lower.startswith("termino clave:"):
            term = focus.split(":", 1)[-1].strip()
            questions.append(f"¿Por qué el término '{term}' es relevante para defender la metodología o los resultados?")
        elif any(word in lower for word in ("resultado", "comparativa", "metodolog", "decid", "seleccion", "eleg")):
            questions.append(f"Explique con sus palabras la decision o resultado descrito aqui: {focus[:120]}")
        if len(questions) >= 6:
            break
    return questions


def _add_defense_questions(summary: dict[str, Any]) -> None:
    review = summary.get("ai_model_review") or {}
    model_questions = [
        str(question).strip()
        for question in (review.get("teacher_questions") or [])
        if str(question).strip() and not _is_generic_question(str(question))
    ]
    fallback = _fallback_teacher_questions(summary)
    combined: list[str] = []
    seen: set[str] = set()
    for question in [*model_questions, *fallback]:
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        combined.append(question)
        if len(combined) >= 8:
            break
    summary["defense_questions"] = combined
    if review:
        review["teacher_questions"] = combined[:8]


def _add_combined_scores(summary: dict[str, Any], sim_rows: list[dict[str, Any]], ai_model: str) -> None:
    review = summary.get("ai_model_review") or {}
    heuristic_ai_risk = _pct(summary.get("ai_style_risk_pct"))
    local_similarity_risk = _local_similarity_risk(sim_rows)
    heuristic_quality = _pct(summary.get("academic_quality_pct"))

    if not review.get("available") or not _has_model_scores(review):
        summary["audit_mode"] = "heuristic_only"
        summary["ai_required"] = False
        summary["ai_model_used"] = ""
        summary["ai_unavailable_reason"] = (
            review.get("error")
            or f"El modelo local {ai_model} no devolvio las metricas obligatorias."
        )
        summary["combined_ai_usage_risk_pct"] = heuristic_ai_risk
        summary["combined_originality_risk_pct"] = local_similarity_risk
        summary["combined_quality_score_pct"] = heuristic_quality
        summary["combined_scoring"] = {
            "ai_usage_risk": "solo heuristica documental; no hubo revision con modelo local",
            "originality_risk": "solo similitud local; no hubo estimacion de originalidad por modelo",
            "quality_score": "solo calidad heuristica; no hubo estimacion por modelo",
        }
        _add_metric_explanations(summary, sim_rows)
        _add_academic_rubric(summary, sim_rows)
        _add_separated_reading(summary, sim_rows)
        _add_defense_questions(summary)
        return

    model_ai_risk = _pct(review.get("ai_usage_risk_pct"))
    model_originality_risk = _pct(review.get("plagiarism_risk_pct"))
    model_quality = _pct(review.get("quality_score_pct"))

    summary["audit_mode"] = "ai_plus_heuristics"
    summary["ai_required"] = True
    summary["ai_model_used"] = review.get("model") or ai_model
    summary["combined_ai_usage_risk_pct"] = round(heuristic_ai_risk * 0.45 + model_ai_risk * 0.55)
    summary["combined_originality_risk_pct"] = max(local_similarity_risk, model_originality_risk)
    summary["combined_quality_score_pct"] = round(heuristic_quality * 0.60 + model_quality * 0.40)
    summary["combined_scoring"] = {
        "ai_usage_risk": "45% heuristica documental + 55% modelo IA local",
        "originality_risk": "maximo entre similitud local y riesgo de originalidad estimado por modelo",
        "quality_score": "60% calidad heuristica + 40% calidad estimada por modelo",
    }
    _add_metric_explanations(summary, sim_rows)
    _add_academic_rubric(summary, sim_rows)
    _add_separated_reading(summary, sim_rows)
    _add_defense_questions(summary)


def run_document_audit(
    docx: Path,
    out_dir: Path,
    results_csv: Path | None = None,
    raw_dir: Path | None = None,
    corpus_dir: Path | None = None,
    min_similarity: int = 82,
    ai_model: str = DEFAULT_AI_MODEL,
    ollama_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    if not docx.exists():
        raise FileNotFoundError(f"Document not found: {docx}")

    out_dir.mkdir(parents=True, exist_ok=True)

    items = read_document_paragraphs(docx)
    if not items:
        raise ValueError(
            "No se pudo extraer texto del documento. Si es PDF escaneado como imagen, hace falta OCR."
        )
    paragraphs = audit_paragraphs(items)
    sections = audit_sections(paragraphs)
    summary: dict[str, Any] = summarize_document(paragraphs, sections)
    if summary.get("scoring_exclusions_active"):
        scored_paragraph_items = [
            (paragraph.index, paragraph.text)
            for paragraph in paragraphs
            if is_scored_source_role(paragraph.source_role)
        ]
    else:
        scored_paragraph_items = [(paragraph.index, paragraph.text) for paragraph in paragraphs]

    experiment = load_results(results_csv, raw_dir)
    if experiment:
        summary["experiment"] = experiment
        summary["experiment_reliability_pct"] = experiment["reliability_pct"]
        summary["academic_quality_pct"] = round(
            max(0, min(100, summary["academic_quality_pct"] * 0.75 + experiment["reliability_pct"] * 0.25))
        )
    else:
        summary["experiment_reliability_pct"] = None

    similarity_result = find_local_matches_with_scope(
        target_docx=docx,
        corpus_dir=corpus_dir,
        min_similarity=min_similarity,
        target_paragraphs=scored_paragraph_items,
    )
    matches = similarity_result["matches"]
    summary["originality_scope"] = similarity_result["scope"]

    p_rows = paragraph_rows(paragraphs)
    s_rows = section_rows(sections)
    sim_rows = similarity_rows(matches)

    model_name = (ai_model or DEFAULT_AI_MODEL).strip() or DEFAULT_AI_MODEL
    document_text = "\n\n".join(text for _, text in scored_paragraph_items)
    summary["ai_model_review"] = run_ollama_review(
        document_text=document_text,
        summary=summary,
        similarity_rows=sim_rows,
        model=model_name,
        base_url=ollama_url,
    )
    _add_combined_scores(summary, sim_rows, model_name)

    write_csv(out_dir / "paragraph_audit.csv", p_rows)
    write_csv(out_dir / "section_audit.csv", s_rows)
    write_csv(out_dir / "similarity_matches.csv", sim_rows)
    write_json(out_dir / "audit_summary.json", summary)
    write_dashboard(out_dir / "dashboard.html", docx.name, summary, p_rows, s_rows, sim_rows)
    write_markdown(out_dir / "quality_audit_report.md", summary, s_rows, sim_rows)
    write_teacher_report(out_dir / "teacher_report.md", docx.name, summary, p_rows, sim_rows)

    return {
        "summary": summary,
        "paragraph_rows": p_rows,
        "section_rows": s_rows,
        "similarity_rows": sim_rows,
        "out_dir": out_dir,
    }
