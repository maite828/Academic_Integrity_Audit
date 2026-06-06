from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from statistics import mean, pstdev


SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9¿¡])")
WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+(?:[-_][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+)?")

CLICHES = [
    "en resumen",
    "en definitiva",
    "es importante destacar",
    "cabe destacar",
    "cabe senalar",
    "cabe señalar",
    "los resultados muestran",
    "los resultados indican",
    "se puede observar",
    "se observa que",
    "por tanto",
    "por lo tanto",
    "asimismo",
    "ademas",
    "además",
    "en este sentido",
    "de forma general",
    "en conclusion",
    "en conclusión",
]
GENERIC_TERMS = [
    "adecuado",
    "conveniente",
    "mejor",
    "superior",
    "estable",
    "razonable",
    "eficiente",
    "significativo",
    "relevante",
    "claro",
    "correcto",
    "util",
    "útil",
    "importante",
    "robusto",
]
FIRST_PERSON = [
    "he seleccionado",
    "he ejecutado",
    "he decidido",
    "he comparado",
    "he usado",
    "he optado",
    "he documentado",
    "he validado",
    "considero",
    "descarto",
    "selecciono",
    "ejecuto",
    "comparo",
    "empleo",
    "uso",
    "documente",
    "documenté",
    "decidi",
    "decidí",
    "seleccioné",
    "ejecuté",
    "analicé",
    "revise",
    "revisé",
]
TRACE_TERMS = [
    "script",
    "csv",
    "salida cruda",
    "salidas crudas",
    "raw",
    "results",
    "preflight",
    "pddl",
    "endpoint",
    "reproducible",
    "solver.planning.domains",
]
METRIC_TERMS = [
    "acciones",
    "coste",
    "costo",
    "metrica",
    "métrica",
    "tiempo",
    "nodos",
    "generados",
    "expandidos",
    "heuristica",
    "heurística",
    "busqueda",
    "búsqueda",
    "plan",
]


@dataclass
class ParagraphAudit:
    index: int
    section: str
    words: int
    sentences: int
    avg_sentence_len: float
    max_sentence_len: int
    first_person_hits: int
    cliche_hits: str
    numeric_anchors: int
    metric_hits: int
    trace_hits: int
    generic_unanchored: int
    repeated_opening: int
    risk_pct: int
    risk_label: str
    note: str
    text: str


@dataclass
class SectionAudit:
    section: str
    paragraphs: int
    words: int
    first_person_hits: int
    cliche_hits: int
    numeric_anchors: int
    metric_hits: int
    trace_hits: int
    generic_unanchored: int
    risk_pct: int
    quality_pct: int


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def sentences(text: str) -> list[str]:
    return [item.strip() for item in SENT_RE.split(text.strip()) if item.strip()]


def count_terms(lower: str, terms: list[str]) -> int:
    return sum(lower.count(term) for term in terms)


def clamp(value: float, lo: int = 0, hi: int = 100) -> float:
    return max(lo, min(hi, value))


def risk_label(score: int) -> str:
    if score >= 70:
        return "alto"
    if score >= 45:
        return "medio"
    if score >= 25:
        return "bajo"
    return "ok"


def audit_paragraphs(items: list[tuple[str, str]]) -> list[ParagraphAudit]:
    openings = []
    for _, text in items:
        w = words(text)
        openings.append(" ".join(w[:4]).lower() if w else "")
    opening_counts = Counter(item for item in openings if item)

    audits: list[ParagraphAudit] = []
    for index, (section, text) in enumerate(items, 1):
        w = words(text)
        sents = sentences(text)
        sent_lengths = [len(words(sentence)) for sentence in sents] or [len(w)]
        lower = text.lower()
        cliche_matches = [cliche for cliche in CLICHES if cliche in lower]
        first_person = count_terms(lower, FIRST_PERSON)
        numeric = len(re.findall(r"\d+(?:[,.]\d+)?", text))
        metric = count_terms(lower, METRIC_TERMS)
        trace = count_terms(lower, TRACE_TERMS)
        generic = int(any(term in lower for term in GENERIC_TERMS) and not (numeric or metric or trace))
        opening = " ".join(w[:4]).lower() if w else ""
        repeated = int(opening_counts.get(opening, 0) >= 2 and len(w) > 35)

        score = 0
        notes: list[str] = []
        if cliche_matches:
            score += min(18, 8 + 3 * len(cliche_matches))
            notes.append("formula or predictable connector")
        if generic:
            score += 20
            notes.append("generic judgement without anchor")
        if len(w) > 120:
            score += 12
            notes.append("very long paragraph")
        elif len(w) > 90:
            score += 6
            notes.append("long paragraph")
        if max(sent_lengths) > 45:
            score += 8
            notes.append("very long sentence")
        elif max(sent_lengths) > 35:
            score += 4
            notes.append("long sentence")
        if len(w) >= 60 and not (numeric or metric or trace):
            score += 10
            notes.append("long paragraph without evidence anchors")
        if repeated:
            score += 5
            notes.append("repeated paragraph opening")

        score -= min(18, 3 * min(numeric, 3) + 2 * min(metric, 3) + 2 * min(trace, 3) + 2 * first_person)
        pct = int(round(clamp(score)))
        audits.append(
            ParagraphAudit(
                index=index,
                section=section,
                words=len(w),
                sentences=len(sents),
                avg_sentence_len=round(mean(sent_lengths), 2) if sent_lengths else 0,
                max_sentence_len=max(sent_lengths) if sent_lengths else 0,
                first_person_hits=first_person,
                cliche_hits="; ".join(cliche_matches),
                numeric_anchors=numeric,
                metric_hits=metric,
                trace_hits=trace,
                generic_unanchored=generic,
                repeated_opening=repeated,
                risk_pct=pct,
                risk_label=risk_label(pct),
                note="; ".join(notes),
                text=text,
            )
        )
    return audits


def audit_sections(paragraphs: list[ParagraphAudit]) -> list[SectionAudit]:
    groups: dict[str, list[ParagraphAudit]] = defaultdict(list)
    for paragraph in paragraphs:
        groups[paragraph.section].append(paragraph)

    sections: list[SectionAudit] = []
    for section, rows in groups.items():
        risk = int(round(mean(row.risk_pct for row in rows))) if rows else 0
        first_person = sum(row.first_person_hits for row in rows)
        numeric = sum(row.numeric_anchors for row in rows)
        metric = sum(row.metric_hits for row in rows)
        trace = sum(row.trace_hits for row in rows)
        generic = sum(row.generic_unanchored for row in rows)
        cliches = sum(1 for row in rows if row.cliche_hits)
        anchor_bonus = clamp(min(numeric, 8) * 2 + min(metric, 10) * 1.8 + min(trace, 8) * 2 + min(first_person, 5) * 3, 0, 45)
        quality = int(round(clamp(92 - risk + anchor_bonus * 0.25 - generic * 4)))
        sections.append(
            SectionAudit(
                section=section,
                paragraphs=len(rows),
                words=sum(row.words for row in rows),
                first_person_hits=first_person,
                cliche_hits=cliches,
                numeric_anchors=numeric,
                metric_hits=metric,
                trace_hits=trace,
                generic_unanchored=generic,
                risk_pct=risk,
                quality_pct=quality,
            )
        )
    return sections


def summarize_document(paragraphs: list[ParagraphAudit], sections: list[SectionAudit]) -> dict:
    all_text = "\n".join(paragraph.text for paragraph in paragraphs)
    all_words = words(all_text)
    all_sentences = sentences(all_text)
    sent_lengths = [len(words(sentence)) for sentence in all_sentences]
    lower = all_text.lower()

    cliche_total = sum(lower.count(cliche) for cliche in CLICHES)
    first_person_total = count_terms(lower, FIRST_PERSON)
    trace_terms = sorted({term for term in TRACE_TERMS if term in lower})
    metric_terms = sorted({term for term in METRIC_TERMS if term in lower})
    high = sum(1 for item in paragraphs if item.risk_pct >= 70)
    medium = sum(1 for item in paragraphs if 45 <= item.risk_pct < 70)
    low = sum(1 for item in paragraphs if 25 <= item.risk_pct < 45)

    paragraph_risk_avg = mean([item.risk_pct for item in paragraphs] or [0])
    stddev = pstdev(sent_lengths) if len(sent_lengths) > 1 else 0
    cliche_component = clamp((cliche_total / max(1, len(all_words))) * 1000 * 12, 0, 25)
    generic_component = clamp((sum(item.generic_unanchored for item in paragraphs) / max(1, len(paragraphs))) * 120, 0, 20)
    uniformity_component = clamp((9 - stddev) * 3, 0, 18)
    low_trace_component = clamp(20 - len(trace_terms) * 2 - len(metric_terms) * 1.2, 0, 20)
    low_personal_component = clamp(12 - first_person_total * 1.2, 0, 12)
    high_para_component = clamp(high * 8 + medium * 4 + low * 1.5, 0, 25)

    risk = round(
        clamp(
            paragraph_risk_avg * 0.45
            + cliche_component
            + generic_component
            + uniformity_component
            + low_trace_component
            + low_personal_component
            + high_para_component
        )
    )
    evidence = clamp(len(trace_terms) * 3 + len(metric_terms) * 2 + first_person_total * 1.5, 0, 45)
    quality = round(clamp(92 - risk * 0.6 + evidence * 0.25))

    return {
        "total_words": len(all_words),
        "total_paragraphs": len(paragraphs),
        "total_sentences": len(all_sentences),
        "avg_sentence_words": round(mean(sent_lengths), 2) if sent_lengths else 0,
        "sentence_stddev": round(stddev, 2),
        "first_person_total": first_person_total,
        "cliche_total": cliche_total,
        "trace_terms_found": trace_terms,
        "metric_terms_found": metric_terms,
        "paragraphs_high_risk": high,
        "paragraphs_medium_risk": medium,
        "paragraphs_low_risk": low,
        "ai_style_risk_pct": risk,
        "academic_quality_pct": quality,
        "components": {
            "paragraph_risk_avg": round(paragraph_risk_avg, 2),
            "cliche_component": round(cliche_component, 2),
            "generic_component": round(generic_component, 2),
            "uniformity_component": round(uniformity_component, 2),
            "low_trace_component": round(low_trace_component, 2),
            "low_personal_component": round(low_personal_component, 2),
            "high_para_component": round(high_para_component, 2),
            "evidence_component": round(evidence, 2),
        },
    }


def paragraph_rows(paragraphs: list[ParagraphAudit]) -> list[dict]:
    return [asdict(item) for item in paragraphs]


def section_rows(sections: list[SectionAudit]) -> list[dict]:
    return [asdict(item) for item in sections]

