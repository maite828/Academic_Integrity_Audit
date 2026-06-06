from __future__ import annotations

import html
import shutil
from pathlib import Path
from zipfile import ZipFile

from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Route

from academic_audit.audit_runner import DEFAULT_AI_MODEL, run_document_audit


RUNS_DIR = Path("runs_form")
APP_PORT = 8601


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def layout(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    body {{ margin:0; font-family:Arial, sans-serif; background:#f6f7fb; color:#172033; }}
    header {{ background:#111827; color:white; padding:22px 28px; }}
    main {{ max-width:980px; margin:0 auto; padding:28px; }}
    .panel {{ background:white; border:1px solid #d9dee8; border-radius:10px; padding:22px; margin-bottom:18px; }}
    label {{ display:block; font-weight:700; margin:16px 0 6px; }}
    input[type="text"], input[type="number"], input[type="file"] {{ width:100%; box-sizing:border-box; padding:11px; border:1px solid #c9d1df; border-radius:8px; }}
    button,.button {{ display:inline-block; background:#2563eb; color:white; border:0; border-radius:8px; padding:12px 18px; font-weight:700; text-decoration:none; cursor:pointer; }}
    .button.secondary {{ background:#374151; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }}
    .metric {{ background:#f1f5f9; border:1px solid #dbe3ee; border-radius:8px; padding:16px; }}
    .metric strong {{ display:block; font-size:28px; margin-top:8px; }}
    .note {{ color:#5b6678; line-height:1.5; }}
    .error {{ background:#fee2e2; border-color:#fecaca; color:#7f1d1d; }}
    @media(max-width:760px) {{ .grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Academic Integrity Audit</h1>
    <p>Formulario local simple: sube un Word o PDF, analiza y descarga resultados.</p>
  </header>
  <main>{body}</main>
</body>
</html>"""
    )


def safe_label(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value).strip("_")
    return cleaned or "audit_run"


async def save_upload(upload: UploadFile | None, destination: Path) -> Path | None:
    if not upload or not upload.filename:
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(await upload.read())
    return destination


async def unzip_upload(upload: UploadFile | None, destination: Path) -> Path | None:
    if not upload or not upload.filename:
        return None
    destination.mkdir(parents=True, exist_ok=True)
    zip_path = destination / Path(upload.filename).name
    zip_path.write_bytes(await upload.read())
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


async def home(_request):
    body = f"""
  <section class="panel">
    <h2>Analizar documento</h2>
    <p class="note">La IA local con Ollama es obligatoria. Modelo por defecto: <strong>{esc(DEFAULT_AI_MODEL)}</strong>.</p>
    <form action="/audit" method="post" enctype="multipart/form-data">
      <label>Documento principal (.docx o .pdf)</label>
      <input type="file" name="docx" accept=".docx,.pdf" required>

      <label>Nombre de la ejecucion</label>
      <input type="text" name="run_label" value="audit_run">

      <label>Modelo Ollama</label>
      <input type="text" name="ai_model" value="{esc(DEFAULT_AI_MODEL)}">

      <label>URL Ollama</label>
      <input type="text" name="ollama_url" value="http://127.0.0.1:11434">

      <label>Umbral de similitud local</label>
      <input type="number" name="min_similarity" value="82" min="70" max="98">

      <details>
        <summary>Opciones avanzadas</summary>
        <label>CSV de resultados experimentales</label>
        <input type="file" name="results_csv" accept=".csv">

        <label>ZIP con salidas raw (.txt)</label>
        <input type="file" name="raw_zip" accept=".zip">

        <label>ZIP con corpus local de documentos (.docx o .pdf)</label>
        <input type="file" name="corpus_zip" accept=".zip">
      </details>

      <p><button type="submit">Analizar documento</button></p>
    </form>
  </section>
"""
    return layout("Academic Integrity Audit", body)


async def audit(request):
    form = await request.form()
    docx_upload = form.get("docx")
    if not isinstance(docx_upload, UploadFile) or not docx_upload.filename:
        return layout("Error", '<section class="panel error">Falta el documento .docx o .pdf.</section>')

    run_id = safe_label(str(form.get("run_label") or "audit_run"))
    run_dir = RUNS_DIR / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)

    input_dir = run_dir / "input"
    out_dir = run_dir / "output"
    input_dir.mkdir(parents=True, exist_ok=True)

    docx_path = await save_upload(docx_upload, input_dir / Path(docx_upload.filename).name)
    results_csv_path = await save_upload(form.get("results_csv"), input_dir / "results.csv")
    raw_dir = await unzip_upload(form.get("raw_zip"), input_dir / "raw_upload")
    corpus_dir = await unzip_upload(form.get("corpus_zip"), input_dir / "corpus_upload")

    try:
        min_similarity = int(str(form.get("min_similarity") or "82"))
    except ValueError:
        min_similarity = 82

    ai_model = str(form.get("ai_model") or DEFAULT_AI_MODEL).strip() or DEFAULT_AI_MODEL
    ollama_url = str(form.get("ollama_url") or "http://127.0.0.1:11434").strip()

    try:
        result = run_document_audit(
            docx=docx_path,
            out_dir=out_dir,
            results_csv=results_csv_path,
            raw_dir=raw_dir,
            corpus_dir=corpus_dir,
            min_similarity=min_similarity,
            ai_model=ai_model,
            ollama_url=ollama_url,
        )
    except Exception as exc:
        body = f"""
  <section class="panel error">
    <h2>No se pudo ejecutar la auditoria</h2>
    <p>{esc(exc)}</p>
    <p>Prepara la IA local con: <code>scripts/setup_ai_local.sh llama3.1</code></p>
    <p><a class="button secondary" href="/">Volver</a></p>
  </section>
"""
        return layout("Error", body)

    summary = result["summary"]
    zip_dir(out_dir, run_dir / "results.zip")

    body = f"""
  <section class="panel">
    <h2>Auditoria completada</h2>
    <div class="grid">
      <div class="metric">Riesgo IA combinado<strong>{summary.get("combined_ai_usage_risk_pct")}%</strong></div>
      <div class="metric">Riesgo originalidad<strong>{summary.get("combined_originality_risk_pct")}%</strong></div>
      <div class="metric">Calidad integral<strong>{summary.get("combined_quality_score_pct")}%</strong></div>
    </div>
    <p class="note">Modelo IA: {esc(summary.get("ai_model_used"))}. Salida local: <code>{esc(out_dir)}</code></p>
    <p>
      <a class="button" href="/view/{esc(run_id)}/dashboard.html" target="_blank">Ver dashboard</a>
      <a class="button secondary" href="/download/{esc(run_id)}/results.zip">Descargar ZIP</a>
      <a class="button secondary" href="/download/{esc(run_id)}/quality_audit_report.md">Markdown</a>
      <a class="button secondary" href="/download/{esc(run_id)}/audit_summary.json">JSON</a>
    </p>
    <p><a href="/">Analizar otro documento</a></p>
  </section>
"""
    return layout("Resultado", body)


async def view_file(_request):
    run_id = safe_label(_request.path_params["run_id"])
    filename = _request.path_params["filename"]
    path = (RUNS_DIR / run_id / "output" / filename).resolve()
    base = (RUNS_DIR / run_id / "output").resolve()
    if not str(path).startswith(str(base)) or not path.exists():
        return PlainTextResponse("Archivo no encontrado.", status_code=404)
    return FileResponse(path)


async def download_file(_request):
    run_id = safe_label(_request.path_params["run_id"])
    filename = _request.path_params["filename"]
    if filename == "results.zip":
        path = RUNS_DIR / run_id / "results.zip"
    else:
        path = RUNS_DIR / run_id / "output" / filename
    if not path.exists():
        return PlainTextResponse("Archivo no encontrado.", status_code=404)
    return FileResponse(path, filename=path.name)


async def health(_request):
    return PlainTextResponse("ok")


routes = [
    Route("/", home, methods=["GET"]),
    Route("/audit", audit, methods=["POST"]),
    Route("/view/{run_id:str}/{filename:path}", view_file, methods=["GET"]),
    Route("/download/{run_id:str}/{filename:path}", download_file, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
]

app = Starlette(routes=routes)
