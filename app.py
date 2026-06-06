from __future__ import annotations

import shutil
from pathlib import Path
from zipfile import ZipFile

import streamlit as st

from academic_audit.audit_runner import DEFAULT_AI_MODEL, run_document_audit


APP_TITLE = "Academic Integrity Audit"
RUNS_DIR = Path("runs")


def save_upload(uploaded_file, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(uploaded_file.getbuffer())
    return destination


def unzip_upload(uploaded_file, destination: Path) -> Path:
    zip_path = destination / uploaded_file.name
    save_upload(uploaded_file, zip_path)
    extract_dir = destination / zip_path.stem
    extract_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)
    return extract_dir


def zip_dir(source_dir: Path, zip_path: Path) -> Path:
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w") as archive:
        for path in source_dir.rglob("*"):
            if path.is_file() and path != zip_path:
                archive.write(path, path.relative_to(source_dir))
    return zip_path


def display_metric(label: str, value):
    st.metric(label, "n/a" if value is None else value)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="doc", layout="wide")

    st.title(APP_TITLE)
    st.caption("Auditoria academica local, gratuita y privada. No sube documentos a servicios externos.")

    with st.sidebar:
        st.header("Uso")
        st.write("1. Sube un documento Word o PDF.")
        st.write("2. Anade CSV/raw si quieres auditar trazabilidad experimental.")
        st.write("3. Anade un ZIP de documentos si quieres similitud local.")
        st.write("4. Pulsa Analizar.")
        st.divider()
        min_similarity = st.slider("Umbral de similitud local", 70, 98, 82)
        st.divider()
        st.subheader("IA local obligatoria")
        st.caption("El informe combina heuristicas locales con un modelo Ollama local.")
        ai_model = st.text_input("Modelo Ollama", value=DEFAULT_AI_MODEL)
        ollama_url = st.text_input("URL Ollama", value="http://127.0.0.1:11434")

    docx_file = st.file_uploader("Documento principal (.docx o .pdf)", type=["docx", "pdf"])

    run_label = st.text_input("Nombre de la ejecucion", value="audit_run")
    results_csv = None
    raw_zip = None
    corpus_zip = None
    with st.expander("Opciones avanzadas: experimento y corpus local"):
        col_left, col_right = st.columns(2)
        with col_left:
            results_csv = st.file_uploader("CSV de resultados experimentales opcional", type=["csv"])
            raw_zip = st.file_uploader("ZIP opcional con salidas raw (.txt)", type=["zip"], key="raw_zip")
        with col_right:
            corpus_zip = st.file_uploader(
                "ZIP opcional con corpus local de documentos .docx o .pdf",
                type=["zip"],
                key="corpus_zip",
            )
            st.caption("La IA local es obligatoria y no sube documentos a servicios externos.")

    analyze = st.button("Analizar documento", type="primary", disabled=docx_file is None)

    if not analyze:
        st.info("Sube un `.docx` o `.pdf` y pulsa Analizar documento.")
        return

    safe_label = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in run_label).strip("_") or "audit_run"
    run_dir = RUNS_DIR / safe_label
    if run_dir.exists():
        shutil.rmtree(run_dir)
    input_dir = run_dir / "input"
    out_dir = run_dir / "output"
    input_dir.mkdir(parents=True, exist_ok=True)

    docx_path = save_upload(docx_file, input_dir / docx_file.name)
    results_csv_path = save_upload(results_csv, input_dir / results_csv.name) if results_csv else None
    raw_dir = unzip_upload(raw_zip, input_dir / "raw_upload") if raw_zip else None
    corpus_dir = unzip_upload(corpus_zip, input_dir / "corpus_upload") if corpus_zip else None

    with st.spinner("Auditando documento..."):
        try:
            result = run_document_audit(
                docx=docx_path,
                out_dir=out_dir,
                results_csv=results_csv_path,
                raw_dir=raw_dir,
                corpus_dir=corpus_dir,
                min_similarity=min_similarity,
                ai_model=ai_model.strip() or DEFAULT_AI_MODEL,
                ollama_url=ollama_url.strip() if ollama_url.strip() else "http://127.0.0.1:11434",
            )
        except Exception as exc:
            st.error(f"No se pudo ejecutar la auditoria: {exc}")
            st.info("Prepara la IA local con: `scripts/setup_ai_local.sh llama3.1`")
            return

    summary = result["summary"]
    similarity_rows = result["similarity_rows"]

    st.success("Auditoria completada.")
    metric_cols = st.columns(4)
    with metric_cols[0]:
        display_metric("Riesgo IA combinado", f"{summary.get('combined_ai_usage_risk_pct')}%")
    with metric_cols[1]:
        display_metric("Riesgo originalidad", f"{summary.get('combined_originality_risk_pct')}%")
    with metric_cols[2]:
        display_metric("Calidad integral", f"{summary.get('combined_quality_score_pct')}%")
    with metric_cols[3]:
        reliability = summary.get("experiment_reliability_pct")
        display_metric("Fiabilidad experimental", f"{reliability}%" if reliability is not None else None)

    st.caption(
        f"Heuristica documental: {summary.get('ai_style_risk_pct')}% riesgo IA, "
        f"{summary.get('academic_quality_pct')}% calidad. Coincidencias locales: {len(similarity_rows)}."
    )

    ai_review = summary.get("ai_model_review")
    st.subheader("Revision con IA local")
    ai_cols = st.columns(3)
    with ai_cols[0]:
        display_metric("Riesgo uso IA", f"{ai_review.get('ai_usage_risk_pct')}%")
    with ai_cols[1]:
        display_metric("Riesgo plagio/originalidad", f"{ai_review.get('plagiarism_risk_pct')}%")
    with ai_cols[2]:
        display_metric("Calidad segun modelo", f"{ai_review.get('quality_score_pct')}%")
    st.write(ai_review.get("overall_verdict") or "")
    with st.expander("Motivos y recomendaciones del modelo"):
        st.write("Motivos de riesgo IA")
        st.write(ai_review.get("ai_risk_reasons") or [])
        st.write("Motivos de originalidad/plagio")
        st.write(ai_review.get("plagiarism_risk_reasons") or [])
        st.write("Recomendaciones")
        st.write(ai_review.get("quality_recommendations") or [])
        st.write("Preguntas de defensa")
        st.write(ai_review.get("teacher_questions") or [])

    st.subheader("Archivos generados")
    dashboard_path = out_dir / "dashboard.html"
    report_path = out_dir / "quality_audit_report.md"
    summary_path = out_dir / "audit_summary.json"
    result_zip = zip_dir(out_dir, run_dir / f"{safe_label}_results.zip")

    download_cols = st.columns(4)
    with download_cols[0]:
        st.download_button("Descargar ZIP", result_zip.read_bytes(), file_name=result_zip.name)
    with download_cols[1]:
        st.download_button("Dashboard HTML", dashboard_path.read_bytes(), file_name="dashboard.html")
    with download_cols[2]:
        st.download_button("Informe Markdown", report_path.read_bytes(), file_name="quality_audit_report.md")
    with download_cols[3]:
        st.download_button("Resumen JSON", summary_path.read_bytes(), file_name="audit_summary.json")

    st.subheader("Vista rapida")
    st.write(f"Salida local: `{out_dir}`")

    if similarity_rows:
        st.subheader("Coincidencias locales")
        st.dataframe(similarity_rows, use_container_width=True)

    with st.expander("Resumen JSON"):
        st.json(summary)


if __name__ == "__main__":
    main()
