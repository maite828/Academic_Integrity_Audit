from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def build_review_prompt(
    document_text: str,
    summary: dict[str, Any],
    similarity_rows: list[dict[str, Any]],
) -> str:
    similarity_sample = similarity_rows[:8]
    return f"""Eres un auditor academico local. Evalua el texto con prudencia.

No afirmes plagio confirmado ni uso de IA confirmado. Devuelve estimaciones de riesgo
explicables, basadas solo en el texto y en las coincidencias locales aportadas.

Responde exclusivamente en JSON valido con esta estructura:
{{
  "ai_usage_risk_pct": 0,
  "plagiarism_risk_pct": 0,
  "quality_score_pct": 0,
  "overall_verdict": "texto breve",
  "ai_risk_reasons": ["motivo"],
  "plagiarism_risk_reasons": ["motivo"],
  "quality_recommendations": ["recomendacion"],
  "teacher_questions": ["pregunta de verificacion"]
}}

Criterios:
- ai_usage_risk_pct: riesgo de estilo compatible con uso intensivo de IA.
- plagiarism_risk_pct: riesgo de originalidad/plagio segun texto y similitud local.
- quality_score_pct: calidad academica estimada.
- Si no hay corpus externo, no inventes coincidencias externas.
- Si el texto esta bien trazado, con primera persona academica o evidencias, baja el riesgo.

Resumen heuristico local:
{json.dumps(summary, ensure_ascii=False)[:5000]}

Coincidencias locales:
{json.dumps(similarity_sample, ensure_ascii=False)[:4000]}

Texto del documento:
{document_text[:12000]}
"""


def extract_json(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def clamp_pct(value: Any) -> int | None:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return None


def normalize_review(payload: dict[str, Any], model: str, raw_response: str) -> dict[str, Any]:
    review = {
        "available": True,
        "model": model,
        "ai_usage_risk_pct": clamp_pct(payload.get("ai_usage_risk_pct")),
        "plagiarism_risk_pct": clamp_pct(payload.get("plagiarism_risk_pct")),
        "quality_score_pct": clamp_pct(payload.get("quality_score_pct")),
        "overall_verdict": str(payload.get("overall_verdict") or "").strip(),
        "ai_risk_reasons": list(payload.get("ai_risk_reasons") or [])[:8],
        "plagiarism_risk_reasons": list(payload.get("plagiarism_risk_reasons") or [])[:8],
        "quality_recommendations": list(payload.get("quality_recommendations") or [])[:8],
        "teacher_questions": list(payload.get("teacher_questions") or [])[:8],
        "raw_response": raw_response[:6000],
        "error": "",
    }
    return review


def run_ollama_review(
    document_text: str,
    summary: dict[str, Any],
    similarity_rows: list[dict[str, Any]],
    model: str,
    base_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    prompt = build_review_prompt(document_text, summary, similarity_rows)
    request_body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
    ).encode("utf-8")
    url = base_url.rstrip("/") + "/api/generate"
    request = urllib.request.Request(
        url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_http = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "available": False,
            "model": model,
            "error": f"Ollama HTTP {exc.code}: {body[:500]}",
        }
    except Exception as exc:
        return {
            "available": False,
            "model": model,
            "error": f"Ollama no disponible en {base_url}: {exc}",
        }

    parsed_http = extract_json(raw_http)
    response_text = str(parsed_http.get("response") or raw_http)
    parsed_review = extract_json(response_text)
    if not parsed_review:
        return {
            "available": False,
            "model": model,
            "raw_response": response_text[:6000],
            "error": "Ollama respondio, pero no devolvio JSON de auditoria parseable.",
        }

    return normalize_review(parsed_review, model=model, raw_response=response_text)

