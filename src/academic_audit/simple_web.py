from __future__ import annotations

import html
import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from starlette.routing import Route

from academic_audit.audit_runner import DEFAULT_AI_MODEL, run_document_audit


RUNS_DIR = Path("runs_form")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
MODEL_PULL_TIMEOUT_SECONDS = 3600
RECOMMENDED_MODELS = [
    {
        "model": "llama3.1",
        "label": "Llama 3.1 8B",
        "profile": "equilibrado",
        "description": "Buena opcion general para auditorias academicas.",
    },
    {
        "model": "qwen2.5",
        "label": "Qwen2.5 7B",
        "profile": "razonamiento",
        "description": "Buen rendimiento local en tareas de analisis y estructura.",
    },
    {
        "model": "mistral",
        "label": "Mistral 7B",
        "profile": "rapido",
        "description": "Modelo ligero y solido para equipos medianos.",
    },
    {
        "model": "gemma3",
        "label": "Gemma 3 4B",
        "profile": "ligero",
        "description": "Opcion pequena para ordenadores con menos memoria.",
    },
    {
        "model": "llama3.2",
        "label": "Llama 3.2 3B",
        "profile": "muy ligero",
        "description": "Respuesta rapida cuando el equipo no soporta modelos grandes.",
    },
]
RECOMMENDED_MODEL_IDS = {item["model"] for item in RECOMMENDED_MODELS}


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
    input[type="text"], input[type="number"], input[type="file"], select {{ width:100%; box-sizing:border-box; padding:11px; border:1px solid #c9d1df; border-radius:8px; }}
    button,.button {{ display:inline-block; background:#2563eb; color:white; border:0; border-radius:8px; padding:12px 18px; font-weight:700; text-decoration:none; cursor:pointer; }}
    .button.secondary {{ background:#374151; }}
    .button.danger {{ background:#b91c1c; }}
    button:disabled {{ opacity:.55; cursor:not-allowed; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }}
    .metric {{ background:#f1f5f9; border:1px solid #dbe3ee; border-radius:8px; padding:16px; }}
    .metric strong {{ display:block; font-size:28px; margin-top:8px; }}
    .note {{ color:#5b6678; line-height:1.5; }}
    .error {{ background:#fee2e2; border-color:#fecaca; color:#7f1d1d; }}
    .status {{ margin-top:10px; padding:11px 12px; border-radius:8px; background:#eef2ff; color:#1e3a8a; border:1px solid #c7d2fe; }}
    .status.error {{ background:#fee2e2; border-color:#fecaca; color:#7f1d1d; }}
    .status.ok {{ background:#dcfce7; border-color:#bbf7d0; color:#14532d; }}
    .progress {{ height:10px; margin-top:10px; border-radius:999px; background:#dbe3ee; overflow:hidden; }}
    .progress span {{ display:block; height:100%; width:0%; background:#2563eb; transition:width .25s ease; }}
    .progress.indeterminate span {{ width:42%; animation:progress-move 1.2s ease-in-out infinite; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-top:16px; }}
    .dashboard-frame {{ width:100%; height:calc(100vh - 300px); min-height:720px; border:1px solid #d9dee8; border-radius:10px; background:white; }}
    @keyframes progress-move {{ 0% {{ transform:translateX(-120%); }} 100% {{ transform:translateX(260%); }} }}
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


def model_aliases(model: str) -> set[str]:
    cleaned = model.strip()
    aliases = {cleaned}
    if ":" not in cleaned:
        aliases.add(f"{cleaned}:latest")
    return aliases


def installed_model_names(payload: dict) -> set[str]:
    names: set[str] = set()
    for item in payload.get("models", []):
        if isinstance(item, dict):
            for key in ("name", "model"):
                value = str(item.get(key) or "").strip()
                if value:
                    names.add(value)
    return names


def ollama_request(
    base_url: str,
    endpoint: str,
    payload: dict | None = None,
    method: str | None = None,
    timeout_seconds: int = 30,
) -> dict:
    url = base_url.rstrip("/") + endpoint
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method or ("POST" if payload is not None else "GET"),
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw else {}


def format_bytes(value: int | float | None) -> str:
    if not value:
        return "0 MB"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def pull_progress_events(model: str, ollama_url: str):
    status = get_model_status(model, ollama_url)
    yield json.dumps(status, ensure_ascii=False) + "\n"
    if not status["ok"] or status["installed"]:
        return

    url = ollama_url.rstrip("/") + "/api/pull"
    request = urllib.request.Request(
        url,
        data=json.dumps({"model": model, "stream": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=MODEL_PULL_TIMEOUT_SECONDS) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = {"ok": True, "installed": False, "model": model, "status": line}
                completed = payload.get("completed")
                total = payload.get("total")
                percent = None
                if completed and total:
                    percent = round(max(0, min(100, 100 * float(completed) / float(total))))
                event = {
                    "ok": True,
                    "installed": False,
                    "model": model,
                    "status": payload.get("status") or "descargando",
                    "digest": payload.get("digest") or "",
                    "completed": completed,
                    "total": total,
                    "completed_label": format_bytes(completed),
                    "total_label": format_bytes(total),
                    "percent": percent,
                    "error": payload.get("error") or "",
                }
                if event["error"]:
                    event["ok"] = False
                yield json.dumps(event, ensure_ascii=False) + "\n"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        yield json.dumps(
            {"ok": False, "installed": False, "model": model, "error": f"Ollama HTTP {exc.code}: {body[:240]}"},
            ensure_ascii=False,
        ) + "\n"
        return
    except Exception as exc:
        yield json.dumps(
            {"ok": False, "installed": False, "model": model, "error": f"No se pudo descargar el modelo: {exc}"},
            ensure_ascii=False,
        ) + "\n"
        return

    yield json.dumps(get_model_status(model, ollama_url), ensure_ascii=False) + "\n"


def get_model_status(model: str, ollama_url: str) -> dict:
    if model not in RECOMMENDED_MODEL_IDS:
        return {
            "ok": False,
            "installed": False,
            "model": model,
            "error": "Modelo no incluido en la lista local recomendada.",
        }
    try:
        payload = ollama_request(ollama_url, "/api/tags", timeout_seconds=15)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "installed": False, "model": model, "error": f"Ollama HTTP {exc.code}: {body[:240]}"}
    except Exception as exc:
        return {"ok": False, "installed": False, "model": model, "error": f"Ollama no disponible: {exc}"}

    installed = installed_model_names(payload)
    return {
        "ok": True,
        "installed": bool(model_aliases(model) & installed),
        "model": model,
        "installed_models": sorted(installed),
        "error": "",
    }


def delete_recommended_model(model: str, ollama_url: str) -> dict:
    status = get_model_status(model, ollama_url)
    if not status["ok"] or not status["installed"]:
        return status
    installed = set(status.get("installed_models") or [])
    delete_name = next((alias for alias in model_aliases(model) if alias in installed), model)
    try:
        ollama_request(
            ollama_url,
            "/api/delete",
            payload={"model": delete_name},
            method="DELETE",
            timeout_seconds=120,
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "installed": True, "model": model, "error": f"Ollama HTTP {exc.code}: {body[:240]}"}
    except Exception as exc:
        return {"ok": False, "installed": True, "model": model, "error": f"No se pudo eliminar el modelo: {exc}"}

    next_status = get_model_status(model, ollama_url)
    next_status["deleted_model"] = delete_name
    return next_status


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


def safe_output_path(run_id: str, filename: str) -> Path | None:
    base = (RUNS_DIR / run_id / "output").resolve()
    path = (base / filename).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return None
    return path


async def home(_request):
    model_options = "\n".join(
        f'<option value="{esc(item["model"])}">{esc(item["label"])} - {esc(item["profile"])}</option>'
        for item in RECOMMENDED_MODELS
    )
    body = f"""
  <section class="panel">
    <h2>Analizar documento</h2>
    <p class="note">La IA local con Ollama mejora el informe, pero la app puede generar una auditoria heuristica si el modelo no esta listo. Modelo por defecto: <strong>{esc(DEFAULT_AI_MODEL)}</strong>.</p>
    <form id="audit_form" action="/audit" method="post" enctype="multipart/form-data">
      <label>Documento principal (.docx o .pdf)</label>
      <input type="file" name="docx" accept=".docx,.pdf" required>

      <label>Nombre de la ejecucion</label>
      <input type="text" name="run_label" value="audit_run">

      <label>Modelo Ollama gratuito recomendado</label>
      <select id="ai_model" name="ai_model">
        {model_options}
      </select>
      <div id="model_status" class="status">Comprobando modelo local...</div>
      <div id="model_progress" class="progress" hidden><span></span></div>
      <div class="actions">
        <button id="download_model" type="button" class="button secondary">Descargar modelo seleccionado</button>
        <button id="delete_model" type="button" class="button danger">Eliminar modelo seleccionado</button>
      </div>
      <label>
        <input id="heuristic_fallback" type="checkbox" name="heuristic_fallback" value="1" checked>
        Permitir analisis solo heuristico si no hay modelo listo
      </label>

      <label>URL Ollama</label>
      <input id="ollama_url" type="text" name="ollama_url" value="{esc(DEFAULT_OLLAMA_URL)}">

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
        <p class="note">El corpus local sirve para comparar contra trabajos o fuentes que tu aportes en un ZIP. Incluye solo .docx o PDF con texto seleccionable; la app no consulta internet ni bases externas.</p>
      </details>

      <p><button type="submit">Analizar documento</button></p>
    </form>
  </section>
  <script>
    const modelStatus = document.getElementById("model_status");
    const modelSelect = document.getElementById("ai_model");
    const ollamaUrl = document.getElementById("ollama_url");
    const downloadButton = document.getElementById("download_model");
    const deleteButton = document.getElementById("delete_model");
    const auditForm = document.getElementById("audit_form");
    const modelProgress = document.getElementById("model_progress");
    const progressBar = modelProgress.querySelector("span");
    const heuristicFallback = document.getElementById("heuristic_fallback");
    let modelReady = false;
    let submittingAfterModelCheck = false;
    deleteButton.disabled = true;

    function setStatus(message, kind) {{
      modelStatus.textContent = message;
      modelStatus.className = "status" + (kind ? " " + kind : "");
    }}

    function setProgress(percent, active) {{
      if (!active) {{
        modelProgress.hidden = true;
        modelProgress.className = "progress";
        progressBar.style.width = "0%";
        return;
      }}
      modelProgress.hidden = false;
      if (percent === null || percent === undefined) {{
        modelProgress.className = "progress indeterminate";
        progressBar.style.width = "42%";
      }} else {{
        modelProgress.className = "progress";
        progressBar.style.width = Math.max(0, Math.min(100, percent)) + "%";
      }}
    }}

    function setModelButtonsBusy(busy) {{
      downloadButton.disabled = busy;
      deleteButton.disabled = busy || !modelReady;
      modelSelect.disabled = busy;
    }}

    function statusUrl() {{
      const params = new URLSearchParams({{
        model: modelSelect.value,
        ollama_url: ollamaUrl.value
      }});
      return "/api/model-status?" + params.toString();
    }}

    async function checkModel() {{
      setProgress(null, false);
      setStatus("Comprobando modelo local...", "");
      try {{
        const response = await fetch(statusUrl());
        const payload = await response.json();
        if (!payload.ok) {{
          modelReady = false;
          deleteButton.disabled = true;
          setStatus(payload.error || "No se pudo comprobar Ollama.", "error");
          return payload;
        }}
        if (payload.installed) {{
          modelReady = true;
          deleteButton.disabled = false;
          setStatus("Modelo instalado y listo: " + payload.model, "ok");
        }} else {{
          modelReady = false;
          deleteButton.disabled = true;
          setStatus("Modelo no instalado: " + payload.model + ". Se descargara al seleccionarlo o al pulsar el boton.", "");
        }}
        return payload;
      }} catch (error) {{
        modelReady = false;
        deleteButton.disabled = true;
        setStatus("No se pudo contactar con la app local: " + error, "error");
        return {{ ok: false, installed: false }};
      }}
    }}

    async function ensureModel() {{
      setStatus("Comprobando modelo seleccionado...", "");
      const current = await checkModel();
      if (!current.ok || current.installed) {{
        return;
      }}
      setProgress(null, true);
      setStatus("Descargando " + modelSelect.value + ". La primera vez puede tardar varios minutos.", "");
      downloadButton.disabled = true;
      setModelButtonsBusy(true);
      try {{
        const response = await fetch("/api/pull-model", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ model: modelSelect.value, ollama_url: ollamaUrl.value }})
        }});
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let lastPayload = null;

        while (true) {{
          const result = await reader.read();
          if (result.done) {{
            break;
          }}
          buffer += decoder.decode(result.value, {{ stream: true }});
          const lines = buffer.split("\\n");
          buffer = lines.pop();
          for (const line of lines) {{
            if (!line.trim()) {{
              continue;
            }}
            const payload = JSON.parse(line);
            lastPayload = payload;
            if (!payload.ok) {{
              modelReady = false;
              setProgress(null, false);
              setStatus(payload.error || "No se pudo descargar el modelo.", "error");
              continue;
            }}
            if (payload.installed) {{
              modelReady = true;
              setProgress(100, true);
              setStatus("Modelo instalado y listo: " + payload.model, "ok");
              continue;
            }}
            let message = payload.status || "Descargando";
            if (payload.percent !== null && payload.percent !== undefined) {{
              setProgress(payload.percent, true);
              message += " " + payload.percent + "%";
            }} else {{
              setProgress(null, true);
            }}
            if (payload.total_label && payload.total_label !== "0 MB") {{
              message += " (" + payload.completed_label + " de " + payload.total_label + ")";
            }}
            setStatus(message, "");
          }}
        }}

        if (buffer.trim()) {{
          const payload = JSON.parse(buffer);
          lastPayload = payload;
          if (payload.ok && payload.installed) {{
            modelReady = true;
            setProgress(100, true);
            setStatus("Modelo instalado y listo: " + payload.model, "ok");
          }}
        }}
        if (!lastPayload) {{
          modelReady = false;
          setProgress(null, false);
          setStatus("No se recibio progreso de Ollama.", "error");
        }}
      }} catch (error) {{
        modelReady = false;
        setProgress(null, false);
        setStatus("Error descargando modelo: " + error, "error");
      }} finally {{
        downloadButton.disabled = false;
        setModelButtonsBusy(false);
      }}
    }}

    async function deleteModel() {{
      if (!modelReady) {{
        setStatus("El modelo seleccionado no esta instalado.", "");
        return;
      }}
      const confirmed = window.confirm(
        "Eliminar " + modelSelect.value + " de Ollama?\\n\\n" +
        "Esto borra el modelo del almacen local de Ollama. No borra logs del sistema ni historial de terminal."
      );
      if (!confirmed) {{
        return;
      }}
      setProgress(null, false);
      setStatus("Eliminando modelo " + modelSelect.value + "...", "");
      setModelButtonsBusy(true);
      try {{
        const response = await fetch("/api/delete-model", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ model: modelSelect.value, ollama_url: ollamaUrl.value }})
        }});
        const payload = await response.json();
        if (payload.ok && !payload.installed) {{
          modelReady = false;
          setStatus("Modelo eliminado de Ollama: " + (payload.deleted_model || payload.model), "");
        }} else if (payload.ok && payload.installed) {{
          modelReady = true;
          setStatus("Ollama todavia informa que el modelo esta instalado: " + payload.model, "error");
        }} else {{
          setStatus(payload.error || "No se pudo eliminar el modelo.", "error");
        }}
      }} catch (error) {{
        setStatus("Error eliminando modelo: " + error, "error");
      }} finally {{
        setModelButtonsBusy(false);
      }}
    }}

    modelSelect.addEventListener("change", ensureModel);
    ollamaUrl.addEventListener("change", checkModel);
    downloadButton.addEventListener("click", ensureModel);
    deleteButton.addEventListener("click", deleteModel);
    auditForm.addEventListener("submit", async function(event) {{
      if (submittingAfterModelCheck || modelReady) {{
        return;
      }}
      event.preventDefault();
      if (heuristicFallback.checked) {{
        setProgress(null, false);
        setStatus("Modelo no listo. Continuando con analisis heuristico.", "");
        submittingAfterModelCheck = true;
        auditForm.submit();
        return;
      }}
      await ensureModel();
      if (modelReady) {{
        submittingAfterModelCheck = true;
        auditForm.submit();
      }}
    }});
    checkModel();
  </script>
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
        run_document_audit(
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

    zip_dir(out_dir, run_dir / "results.zip")
    return RedirectResponse(f"/result/{run_id}", status_code=303)


async def result_page(_request):
    run_id = safe_label(_request.path_params["run_id"])
    out_dir = RUNS_DIR / run_id / "output"
    summary_path = out_dir / "audit_summary.json"
    dashboard_path = out_dir / "dashboard.html"
    zip_path = RUNS_DIR / run_id / "results.zip"
    if not summary_path.exists() or not dashboard_path.exists():
        return layout(
            "Resultado no encontrado",
            '<section class="panel error">No se encontro la auditoria solicitada. <a href="/">Volver</a></section>',
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    mode_label = "IA local + heuristicas" if summary.get("audit_mode") == "ai_plus_heuristics" else "solo heuristicas"
    model_label = summary.get("ai_model_used") or "sin modelo local"
    scoring_label = (
        f"Texto puntuado: {summary.get('scored_words', summary.get('total_words', 0))} "
        f"de {summary.get('total_words', 0)} palabras"
    )
    originality_scope = summary.get("originality_scope") or {}
    originality_label = (
        f"Originalidad local: {originality_scope.get('comparable_paragraphs', 0)} parrafos comparables, "
        f"{originality_scope.get('ignored_paragraphs', 0)} ignorados"
    )
    ai_review = summary.get("ai_model_review") or {}
    confidence_label = (
        f"Confianza modelo: {ai_review.get('confidence_pct', 0)}% "
        f"({ai_review.get('confidence_label', 'n/a')})"
        if ai_review.get("available")
        else "Confianza modelo: no disponible"
    )
    body = f"""
  <section class="panel">
    <h2>Auditoria completada</h2>
    <div class="grid">
      <div class="metric">Riesgo IA combinado<strong>{summary.get("combined_ai_usage_risk_pct")}%</strong></div>
      <div class="metric">Riesgo originalidad<strong>{summary.get("combined_originality_risk_pct")}%</strong></div>
      <div class="metric">Calidad integral<strong>{summary.get("combined_quality_score_pct")}%</strong></div>
    </div>
    <p class="note">Modo: {esc(mode_label)}. Modelo IA: {esc(model_label)}. {esc(confidence_label)}. {esc(scoring_label)}. {esc(originality_label)}. Salida local: <code>{esc(out_dir)}</code></p>
    <div class="actions">
      <a class="button" href="/view/{esc(run_id)}/dashboard.html" target="_blank">Abrir dashboard completo</a>
      <a class="button secondary" href="/download/{esc(run_id)}/results.zip">Descargar ZIP</a>
      <a class="button secondary" href="/download/{esc(run_id)}/teacher_report.md">Informe profesor</a>
      <a class="button secondary" href="/download/{esc(run_id)}/quality_audit_report.md">Markdown</a>
      <a class="button secondary" href="/download/{esc(run_id)}/audit_summary.json">JSON</a>
      <a href="/">Analizar otro documento</a>
    </div>
  </section>
  <iframe class="dashboard-frame" src="/view/{esc(run_id)}/dashboard.html" title="Dashboard de auditoria"></iframe>
"""
    if not zip_path.exists():
        zip_dir(out_dir, zip_path)
    return layout("Dashboard", body)


async def view_file(_request):
    run_id = safe_label(_request.path_params["run_id"])
    filename = _request.path_params["filename"]
    path = safe_output_path(run_id, filename)
    if path is None or not path.exists():
        return PlainTextResponse("Archivo no encontrado.", status_code=404)
    return FileResponse(path)


async def download_file(_request):
    run_id = safe_label(_request.path_params["run_id"])
    filename = _request.path_params["filename"]
    if filename == "results.zip":
        path = RUNS_DIR / run_id / "results.zip"
    else:
        path = safe_output_path(run_id, filename)
    if path is None:
        return PlainTextResponse("Archivo no encontrado.", status_code=404)
    if not path.exists():
        return PlainTextResponse("Archivo no encontrado.", status_code=404)
    return FileResponse(path, filename=path.name)


async def health(_request):
    return PlainTextResponse("ok")


async def model_status(request):
    model = str(request.query_params.get("model") or DEFAULT_AI_MODEL).strip()
    ollama_url = str(request.query_params.get("ollama_url") or DEFAULT_OLLAMA_URL).strip()
    return JSONResponse(get_model_status(model, ollama_url))


async def pull_model(request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    model = str(payload.get("model") or DEFAULT_AI_MODEL).strip()
    ollama_url = str(payload.get("ollama_url") or DEFAULT_OLLAMA_URL).strip()
    return StreamingResponse(
        pull_progress_events(model, ollama_url),
        media_type="application/x-ndjson",
    )


async def delete_model(request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    model = str(payload.get("model") or DEFAULT_AI_MODEL).strip()
    ollama_url = str(payload.get("ollama_url") or DEFAULT_OLLAMA_URL).strip()
    return JSONResponse(delete_recommended_model(model, ollama_url))


routes = [
    Route("/", home, methods=["GET"]),
    Route("/audit", audit, methods=["POST"]),
    Route("/result/{run_id:str}", result_page, methods=["GET"]),
    Route("/view/{run_id:str}/{filename:path}", view_file, methods=["GET"]),
    Route("/download/{run_id:str}/{filename:path}", download_file, methods=["GET"]),
    Route("/api/model-status", model_status, methods=["GET"]),
    Route("/api/pull-model", pull_model, methods=["POST"]),
    Route("/api/delete-model", delete_model, methods=["POST"]),
    Route("/health", health, methods=["GET"]),
]

app = Starlette(routes=routes)
