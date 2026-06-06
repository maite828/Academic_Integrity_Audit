from __future__ import annotations

import argparse
from pathlib import Path

from academic_audit.audit_runner import run_document_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="academic-audit",
        description="Local academic integrity, originality and traceability audit.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Audit a DOCX and produce reports.")
    audit.add_argument("docx", type=Path)
    audit.add_argument("--results-csv", type=Path)
    audit.add_argument("--raw-dir", type=Path)
    audit.add_argument("--corpus-dir", type=Path, help="Optional local DOCX corpus for similarity checks.")
    audit.add_argument("--out-dir", type=Path, default=Path("audit_output"))
    audit.add_argument("--min-similarity", type=int, default=82)
    audit.add_argument("--ai-model", help="Optional local Ollama model, for example llama3.1 or mistral.")
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
    print(f"Riesgo heuristico: {summary['ai_style_risk_pct']}%")
    print(f"Calidad academica: {summary['academic_quality_pct']}%")
    if summary.get("experiment_reliability_pct") is not None:
        print(f"Fiabilidad experimental: {summary['experiment_reliability_pct']}%")
    review = summary.get("ai_model_review")
    if review:
        if review.get("available"):
            print(f"Modelo IA local: {review.get('model')}")
            print(f"Riesgo uso IA estimado por modelo: {review.get('ai_usage_risk_pct')}%")
            print(f"Riesgo plagio/originalidad estimado por modelo: {review.get('plagiarism_risk_pct')}%")
        else:
            print(f"Revision IA local no disponible: {review.get('error')}")
    print(f"Coincidencias locales: {len(sim_rows)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "audit":
        return run_audit(args)
    parser.error("Unknown command")
    return 2
