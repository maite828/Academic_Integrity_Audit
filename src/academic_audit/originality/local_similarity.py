from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

from academic_audit.document.docx_reader import read_document_paragraphs
from academic_audit.document.style_audit import words


MIN_SIMILARITY_WORDS = 25
MIN_UNIQUE_WORDS = 14


@dataclass
class SimilarityMatch:
    source_kind: str
    source_doc: str
    source_paragraph: int
    target_paragraph: int
    similarity_pct: int
    target_excerpt: str
    source_excerpt: str


def normalize(text: str) -> str:
    return " ".join(word.lower() for word in words(text))


def comparability_status(text: str) -> tuple[bool, str]:
    text_words = words(text)
    if len(text_words) < MIN_SIMILARITY_WORDS:
        return False, "texto demasiado corto"
    unique_words = {word.lower() for word in text_words if len(word) > 2}
    if len(unique_words) < MIN_UNIQUE_WORDS:
        return False, "poca variedad lexica"
    lower = text.lower()
    if "·" in text and len(text_words) < 35:
        return False, "cabecera o linea de plantilla"
    if lower.startswith(("tabla ", "figura ")) and len(text_words) < 45:
        return False, "tabla o figura demasiado breve"
    boilerplate_terms = [
        "memoria explicativa",
        "actividad 2",
        "actividad 3",
        "asignatura",
        "datos del alumno",
        "datos del equipo",
        "fecha",
    ]
    if len(text_words) < 35 and sum(1 for term in boilerplate_terms if term in lower) >= 2:
        return False, "metadatos o plantilla"
    return True, "comparable"


def is_comparable_text(text: str) -> bool:
    return comparability_status(text)[0]


def paragraph_similarity(left: str, right: str) -> int:
    if not is_comparable_text(left) or not is_comparable_text(right):
        return 0
    left_norm = normalize(left)
    right_norm = normalize(right)
    return int(round(SequenceMatcher(None, left_norm, right_norm).ratio() * 100))


def originality_scope(
    numbered_target_paragraphs: list[tuple[int, str]],
    min_similarity: int,
    corpus_document_names: list[str],
    unreadable_corpus_documents: list[str],
    relevant_matches: int,
    max_observed_similarity_pct: int,
) -> dict:
    ignored_reasons: dict[str, int] = {}
    comparable = 0
    comparable_words = 0
    ignored_words = 0
    ignored_examples: list[dict] = []
    for index, text in numbered_target_paragraphs:
        ok, reason = comparability_status(text)
        text_words = len(words(text))
        if ok:
            comparable += 1
            comparable_words += text_words
            continue
        ignored_words += text_words
        ignored_reasons[reason] = ignored_reasons.get(reason, 0) + 1
        if len(ignored_examples) < 6:
            ignored_examples.append(
                {
                    "paragraph": index,
                    "reason": reason,
                    "words": text_words,
                    "excerpt": text[:180],
                }
            )

    total = len(numbered_target_paragraphs)
    return {
        "threshold_pct": min_similarity,
        "target_paragraphs": total,
        "comparable_paragraphs": comparable,
        "ignored_paragraphs": total - comparable,
        "comparable_words": comparable_words,
        "ignored_words": ignored_words,
        "ignored_reasons": ignored_reasons,
        "ignored_examples": ignored_examples,
        "relevant_matches": relevant_matches,
        "max_observed_similarity_pct": max_observed_similarity_pct,
        "corpus_documents": len(corpus_document_names),
        "corpus_document_names": corpus_document_names,
        "unreadable_corpus_documents": unreadable_corpus_documents,
        "corpus_enabled": bool(corpus_document_names),
        "method": (
            "Compara parrafos suficientemente largos y variados contra repeticiones internas "
            "y, si se aporta, contra corpus local DOCX/PDF."
        ),
        "limitation": "No consulta internet ni bases externas; no equivale a Turnitin.",
    }


def find_local_matches(
    target_docx: Path,
    corpus_dir: Path | None,
    min_similarity: int = 82,
    max_matches: int = 50,
    target_paragraphs: list[tuple[int, str]] | None = None,
) -> list[SimilarityMatch]:
    result = find_local_matches_with_scope(
        target_docx=target_docx,
        corpus_dir=corpus_dir,
        min_similarity=min_similarity,
        max_matches=max_matches,
        target_paragraphs=target_paragraphs,
    )
    return result["matches"]


def find_local_matches_with_scope(
    target_docx: Path,
    corpus_dir: Path | None,
    min_similarity: int = 82,
    max_matches: int = 50,
    target_paragraphs: list[tuple[int, str]] | None = None,
) -> dict:
    if target_paragraphs is None:
        target_items = read_document_paragraphs(target_docx)
        numbered_target_paragraphs = [(index, text) for index, (_, text) in enumerate(target_items, 1)]
    else:
        numbered_target_paragraphs = target_paragraphs
    matches: list[SimilarityMatch] = []

    docs: list[Path] = []
    if corpus_dir and corpus_dir.exists():
        docs.extend(path for path in corpus_dir.rglob("*.docx") if path.resolve() != target_docx.resolve())
        docs.extend(path for path in corpus_dir.rglob("*.pdf") if path.resolve() != target_docx.resolve())

    # Always include internal similarity as a baseline originality signal.
    internal_docs = [(target_docx.name, numbered_target_paragraphs)]
    external_docs: list[tuple[str, list[str]]] = []
    unreadable_docs: list[str] = []
    for doc in docs:
        try:
            external_docs.append((str(doc), [text for _, text in read_document_paragraphs(doc)]))
        except Exception:
            unreadable_docs.append(str(doc))
            continue

    max_observed_similarity_pct = 0
    for doc_name, source_paragraphs in [*internal_docs, *external_docs]:
        source_kind = "interna" if doc_name == target_docx.name else "corpus local"
        seen_internal_pairs: set[tuple[int, int]] = set()
        for target_index, target_text in numbered_target_paragraphs:
            for source_position, source_item in enumerate(source_paragraphs, 1):
                if doc_name == target_docx.name:
                    source_index, source_text = source_item
                else:
                    source_index, source_text = source_position, source_item
                if doc_name == target_docx.name and abs(target_index - source_index) <= 1:
                    continue
                if doc_name == target_docx.name:
                    pair = tuple(sorted((target_index, source_index)))
                    if pair in seen_internal_pairs:
                        continue
                score = paragraph_similarity(target_text, source_text)
                max_observed_similarity_pct = max(max_observed_similarity_pct, score)
                if score >= min_similarity:
                    if doc_name == target_docx.name:
                        seen_internal_pairs.add(tuple(sorted((target_index, source_index))))
                    matches.append(
                        SimilarityMatch(
                            source_kind=source_kind,
                            source_doc=doc_name,
                            source_paragraph=source_index,
                            target_paragraph=target_index,
                            similarity_pct=score,
                            target_excerpt=target_text[:320],
                            source_excerpt=source_text[:320],
                        )
                    )

    matches.sort(key=lambda item: item.similarity_pct, reverse=True)
    matches = matches[:max_matches]
    return {
        "matches": matches,
        "scope": originality_scope(
            numbered_target_paragraphs=numbered_target_paragraphs,
            min_similarity=min_similarity,
            corpus_document_names=[doc_name for doc_name, _ in external_docs],
            unreadable_corpus_documents=unreadable_docs,
            relevant_matches=len(matches),
            max_observed_similarity_pct=max_observed_similarity_pct,
        ),
    }


def similarity_rows(matches: list[SimilarityMatch]) -> list[dict]:
    return [asdict(item) for item in matches]
