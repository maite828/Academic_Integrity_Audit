from __future__ import annotations

from pathlib import Path
from typing import Any

from academic_audit.document.docx_reader import read_docx_paragraphs
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


def run_document_audit(
    docx: Path,
    out_dir: Path,
    results_csv: Path | None = None,
    raw_dir: Path | None = None,
    corpus_dir: Path | None = None,
    min_similarity: int = 82,
    ai_model: str | None = None,
    ollama_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    if not docx.exists():
        raise FileNotFoundError(f"DOCX not found: {docx}")

    out_dir.mkdir(parents=True, exist_ok=True)

    items = read_docx_paragraphs(docx)
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

    if ai_model:
        document_text = "\n\n".join(text for _, text in items)
        summary["ai_model_review"] = run_ollama_review(
            document_text=document_text,
            summary=summary,
            similarity_rows=sim_rows,
            model=ai_model,
            base_url=ollama_url,
        )
    else:
        summary["ai_model_review"] = None

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
