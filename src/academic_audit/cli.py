from __future__ import annotations

import argparse
from pathlib import Path

from academic_audit.audit_runner import DEFAULT_AI_MODEL, run_document_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="academic-audit",
        description="Local academic integrity, originality and traceability audit.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Audit a DOCX or text-based PDF and produce reports.")
    audit.add_argument("docx", type=Path)
    audit.add_argument("--results-csv", type=Path)
    audit.add_argument("--raw-dir", type=Path)
    audit.add_argument("--corpus-dir", type=Path, help="Optional local DOCX/PDF corpus for similarity checks.")
    audit.add_argument("--out-dir", type=Path, default=Path("audit_output"))
    audit.add_argument("--min-similarity", type=int, default=82)
    audit.add_argument(
        "--ai-model",
        default=DEFAULT_AI_MODEL,
        help=f"Local Ollama model used when available. Default: {DEFAULT_AI_MODEL}.",
    )
    audit.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    return parser


def run_audit(args: argparse.Namespace) -> int:
    result = run_document_audit(
        docx=args.docx,
        out_dir=args.out_dir,
        results_csv=args.results_csv,
        raw_dir=args.raw_dir,
        corpus_dir=args.corpus_dir,
        min_similarity=args.min_similarity,
        ai_model=args.ai_model,
        ollama_url=args.ollama_url,
    )
    summary = result["summary"]
    sim_rows = result["similarity_rows"]

    print(f"OK dashboard: {args.out_dir / 'dashboard.html'}")
    has_ai_review = summary.get("audit_mode") == "ai_plus_heuristics"
    print(f"Modo auditoria: {summary.get('audit_mode', 'n/a')}")
    print(f"{'Riesgo IA combinado' if has_ai_review else 'Riesgo estilo IA'}: {summary['combined_ai_usage_risk_pct']}%")
    print(
        f"{'Riesgo originalidad combinado' if has_ai_review else 'Riesgo similitud local'}: "
        f"{summary['combined_originality_risk_pct']}%"
    )
    print(f"{'Calidad integral' if has_ai_review else 'Calidad heuristica'}: {summary['combined_quality_score_pct']}%")
    print(f"Riesgo heuristico: {summary['ai_style_risk_pct']}%")
    print(f"Calidad academica: {summary['academic_quality_pct']}%")
    print(f"Texto puntuado: {summary.get('scored_words', summary.get('total_words', 0))}/{summary.get('total_words', 0)} palabras")
    originality_scope = summary.get("originality_scope") or {}
    print(
        "Originalidad local: "
        f"{originality_scope.get('comparable_paragraphs', 0)} parrafos comparables, "
        f"{originality_scope.get('ignored_paragraphs', 0)} ignorados"
    )
    if summary.get("experiment_reliability_pct") is not None:
        print(f"Fiabilidad experimental: {summary['experiment_reliability_pct']}%")
    review = summary.get("ai_model_review")
    if review and review.get("available"):
        print(f"Modelo IA local: {review.get('model')}")
        print(f"Riesgo uso IA estimado por modelo: {review.get('ai_usage_risk_pct')}%")
        print(f"Riesgo plagio/originalidad estimado por modelo: {review.get('plagiarism_risk_pct')}%")
    print(f"Coincidencias locales: {len(sim_rows)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "audit":
        return run_audit(args)
    parser.error("Unknown command")
    return 2
