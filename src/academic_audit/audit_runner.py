from __future__ import annotations

from pathlib import Path
from typing import Any

from academic_audit.document.docx_reader import read_document_paragraphs
from academic_audit.document.style_audit import (
    audit_paragraphs,
    audit_sections,
    paragraph_rows,
    section_rows,
    summarize_document,
)
from academic_audit.ai.ollama_review import run_ollama_review
from academic_audit.experiment.results_audit import load_results
from academic_audit.originality.local_similarity import find_local_matches, similarity_rows
from academic_audit.reports.dashboard import write_dashboard, write_markdown
from academic_audit.reports.writers import write_csv, write_json


DEFAULT_AI_MODEL = "llama3.1"


def _pct(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return 0


def _local_similarity_risk(sim_rows: list[dict[str, Any]]) -> int:
    values = [_pct(row.get("similarity_pct")) for row in sim_rows]
    return max(values, default=0)


def _add_combined_scores(summary: dict[str, Any], sim_rows: list[dict[str, Any]], ai_model: str) -> None:
    review = summary.get("ai_model_review") or {}
    if not review.get("available"):
        raise RuntimeError(
            "La revision IA local es obligatoria, pero no se pudo ejecutar. "
            f"Modelo: {ai_model}. Error: {review.get('error') or 'sin detalle'}. "
            "Ejecuta scripts/setup_ai_local.sh llama3.1 y reintenta."
        )

    heuristic_ai_risk = _pct(summary.get("ai_style_risk_pct"))
    model_ai_risk = _pct(review.get("ai_usage_risk_pct"))
    local_similarity_risk = _local_similarity_risk(sim_rows)
    model_originality_risk = _pct(review.get("plagiarism_risk_pct"))
    heuristic_quality = _pct(summary.get("academic_quality_pct"))
    model_quality = _pct(review.get("quality_score_pct"))

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

    experiment = load_results(results_csv, raw_dir)
    if experiment:
        summary["experiment"] = experiment
        summary["experiment_reliability_pct"] = experiment["reliability_pct"]
        summary["academic_quality_pct"] = round(
            max(0, min(100, summary["academic_quality_pct"] * 0.75 + experiment["reliability_pct"] * 0.25))
        )
    else:
        summary["experiment_reliability_pct"] = None

    matches = find_local_matches(
        target_docx=docx,
        corpus_dir=corpus_dir,
        min_similarity=min_similarity,
    )

    p_rows = paragraph_rows(paragraphs)
    s_rows = section_rows(sections)
    sim_rows = similarity_rows(matches)

    model_name = (ai_model or DEFAULT_AI_MODEL).strip() or DEFAULT_AI_MODEL
    document_text = "\n\n".join(text for _, text in items)
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

    return {
        "summary": summary,
        "paragraph_rows": p_rows,
        "section_rows": s_rows,
        "similarity_rows": sim_rows,
        "out_dir": out_dir,
    }
