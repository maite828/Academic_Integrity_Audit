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
    defense_focus = summary.get("defense_focus") or []
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
- Las teacher_questions deben ser concretas y citar conceptos, metricas, tablas, figuras,
  decisiones metodologicas o resultados presentes en el texto.
- Evita preguntas genericas como "explique su trabajo"; deben ayudar a verificar autoria
  y comprension real del contenido.

Resumen heuristico local:
{json.dumps(summary, ensure_ascii=False)[:5000]}

Coincidencias locales:
{json.dumps(similarity_sample, ensure_ascii=False)[:4000]}

Focos concretos para preguntas de defensa:
{json.dumps(defense_focus[:12], ensure_ascii=False)[:3000]}

Texto del documento:
{document_text[:12000]}
"""


def build_strict_retry_prompt(
    document_text: str,
    summary: dict[str, Any],
    similarity_rows: list[dict[str, Any]],
    previous_response: str,
) -> str:
    defense_focus = summary.get("defense_focus") or []
    return f"""Tu respuesta anterior no siguio el formato requerido.

Devuelve SOLO este objeto JSON, sin otras claves, sin markdown y sin texto adicional:
{{
  "ai_usage_risk_pct": 0,
  "plagiarism_risk_pct": 0,
  "quality_score_pct": 0,
  "overall_verdict": "maximo 25 palabras",
  "ai_risk_reasons": ["maximo 6 motivos breves"],
  "plagiarism_risk_reasons": ["maximo 6 motivos breves"],
  "quality_recommendations": ["maximo 6 recomendaciones breves"],
  "teacher_questions": ["maximo 6 preguntas breves"]
}}

Reglas:
- Las tres metricas deben ser numeros enteros de 0 a 100.
- No uses claves response_0, content, role, id ni objetos anidados.
- No inventes busqueda web ni plagio externo.
- Si hay evidencias, metricas, primera persona o trazabilidad, baja el riesgo IA.
- Evalua con prudencia: riesgo no equivale a prueba.
- Las teacher_questions deben mencionar elementos concretos del texto: metricas, tablas,
  figuras, parametros, decisiones metodologicas o conclusiones.

Resumen heuristico:
{json.dumps(summary, ensure_ascii=False)[:3000]}

Coincidencias locales:
{json.dumps(similarity_rows[:5], ensure_ascii=False)[:2000]}

Focos concretos para preguntas de defensa:
{json.dumps(defense_focus[:12], ensure_ascii=False)[:3000]}

Texto:
{document_text[:8000]}

Respuesta anterior incorrecta:
{previous_response[:2000]}
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


def clean_model_text(value: Any) -> str:
    text = str(value or "").strip()
    lower = text.lower()
    placeholders = {
        "texto breve",
        "motivo",
        "recomendacion",
        "recomendación",
        "pregunta de verificacion",
        "pregunta de verificación",
        "maximo 25 palabras",
    }
    if lower in placeholders or lower.startswith("maximo "):
        return ""
    return text


def clean_model_list(value: Any, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = clean_model_text(item)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def is_concrete_question(question: str) -> bool:
    lower = question.lower()
    concrete_terms = [
        "tabla",
        "figura",
        "métrica",
        "metrica",
        "parámetro",
        "parametro",
        "resultado",
        "técnica",
        "tecnica",
        "método",
        "metodo",
        "script",
        "modelo",
    ]
    return len(question.split()) >= 9 and any(term in lower for term in concrete_terms)


def confidence_label(score: int) -> str:
    if score >= 80:
        return "alta"
    if score >= 60:
        return "media"
    return "baja"


def add_confidence(review: dict[str, Any]) -> dict[str, Any]:
    if not review.get("available"):
        review["confidence_pct"] = 0
        review["confidence_label"] = "no disponible"
        review["confidence_reasons"] = []
        review["confidence_warnings"] = [review.get("error") or "Modelo no disponible."]
        return review

    reasons: list[str] = ["metricas obligatorias presentes"]
    warnings: list[str] = []
    score = 60

    if review.get("overall_verdict"):
        score += 6
        reasons.append("veredicto textual especifico")
    else:
        score -= 8
        warnings.append("el modelo no produjo un veredicto textual util")

    reason_count = len(review.get("ai_risk_reasons") or []) + len(review.get("plagiarism_risk_reasons") or [])
    if reason_count >= 4:
        score += 10
        reasons.append("motivos suficientes para riesgos principales")
    elif reason_count >= 2:
        score += 5
        reasons.append("motivos minimos para riesgos principales")
    else:
        score -= 12
        warnings.append("pocos motivos explicativos del modelo")

    if len(review.get("quality_recommendations") or []) >= 2:
        score += 5
        reasons.append("recomendaciones de calidad presentes")
    else:
        score -= 4
        warnings.append("pocas recomendaciones de calidad")

    questions = review.get("teacher_questions") or []
    concrete_questions = [question for question in questions if is_concrete_question(str(question))]
    if len(concrete_questions) >= 3:
        score += 10
        reasons.append("preguntas de defensa concretas")
    elif concrete_questions:
        score += 4
        reasons.append("alguna pregunta de defensa concreta")
    else:
        score -= 10
        warnings.append("preguntas de defensa poco concretas o ausentes")

    if review.get("retry_used"):
        score -= 10
        warnings.append("se necesito reintento estricto para obtener JSON valido")

    review["confidence_pct"] = max(0, min(100, int(round(score))))
    review["confidence_label"] = confidence_label(review["confidence_pct"])
    review["confidence_reasons"] = reasons
    review["confidence_warnings"] = warnings
    return review


def normalize_review(payload: dict[str, Any], model: str, raw_response: str) -> dict[str, Any]:
    ai_usage = clamp_pct(payload.get("ai_usage_risk_pct"))
    plagiarism = clamp_pct(payload.get("plagiarism_risk_pct"))
    quality = clamp_pct(payload.get("quality_score_pct"))
    if ai_usage is None or plagiarism is None or quality is None:
        return {
            "available": False,
            "model": model,
            "raw_response": raw_response[:6000],
            "error": (
                "Ollama respondio con JSON, pero no incluyo las metricas obligatorias "
                "ai_usage_risk_pct, plagiarism_risk_pct y quality_score_pct."
            ),
        }

    review = {
        "available": True,
        "model": model,
        "ai_usage_risk_pct": ai_usage,
        "plagiarism_risk_pct": plagiarism,
        "quality_score_pct": quality,
        "overall_verdict": clean_model_text(payload.get("overall_verdict")),
        "ai_risk_reasons": clean_model_list(payload.get("ai_risk_reasons")),
        "plagiarism_risk_reasons": clean_model_list(payload.get("plagiarism_risk_reasons")),
        "quality_recommendations": clean_model_list(payload.get("quality_recommendations")),
        "teacher_questions": clean_model_list(payload.get("teacher_questions")),
        "raw_response": raw_response[:6000],
        "error": "",
    }
    return add_confidence(review)


def run_ollama_review(
    document_text: str,
    summary: dict[str, Any],
    similarity_rows: list[dict[str, Any]],
    model: str,
    base_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    prompt = build_review_prompt(document_text, summary, similarity_rows)

    def generate(prompt_text: str) -> str:
        request_body = json.dumps(
            {
                "model": model,
                "prompt": prompt_text,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0, "num_ctx": 8192},
            }
        ).encode("utf-8")
        url = base_url.rstrip("/") + "/api/generate"
        request = urllib.request.Request(
            url,
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")

    try:
        raw_http = generate(prompt)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return add_confidence({
            "available": False,
            "model": model,
            "error": f"Ollama HTTP {exc.code}: {body[:500]}",
        })
    except Exception as exc:
        return add_confidence({
            "available": False,
            "model": model,
            "error": f"Ollama no disponible en {base_url}: {exc}",
        })

    parsed_http = extract_json(raw_http)
    response_text = str(parsed_http.get("response") or raw_http)
    parsed_review = extract_json(response_text)
    if parsed_review:
        review = normalize_review(parsed_review, model=model, raw_response=response_text)
        if review.get("available"):
            return review

    retry_prompt = build_strict_retry_prompt(document_text, summary, similarity_rows, response_text)
    try:
        retry_raw_http = generate(retry_prompt)
    except Exception:
        retry_raw_http = ""

    if retry_raw_http:
        retry_http = extract_json(retry_raw_http)
        retry_response_text = str(retry_http.get("response") or retry_raw_http)
        retry_review = extract_json(retry_response_text)
        if retry_review:
            review = normalize_review(retry_review, model=model, raw_response=retry_response_text)
            if review.get("available"):
                review["retry_used"] = True
                return add_confidence(review)

    return add_confidence({
        "available": False,
        "model": model,
        "raw_response": response_text[:6000],
        "error": "Ollama respondio, pero no devolvio JSON de auditoria con metricas obligatorias.",
    })
