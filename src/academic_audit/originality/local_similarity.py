from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

from academic_audit.document.docx_reader import read_docx_paragraphs
from academic_audit.document.style_audit import words


@dataclass
class SimilarityMatch:
    source_doc: str
    source_paragraph: int
    target_paragraph: int
    similarity_pct: int
    target_excerpt: str
    source_excerpt: str


def normalize(text: str) -> str:
    return " ".join(word.lower() for word in words(text))


def paragraph_similarity(left: str, right: str) -> int:
    left_norm = normalize(left)
    right_norm = normalize(right)
    if len(left_norm) < 80 or len(right_norm) < 80:
        return 0
    return int(round(SequenceMatcher(None, left_norm, right_norm).ratio() * 100))


def find_local_matches(
    target_docx: Path,
    corpus_dir: Path | None,
    min_similarity: int = 82,
    max_matches: int = 50,
) -> list[SimilarityMatch]:
    target_items = read_docx_paragraphs(target_docx)
    target_paragraphs = [text for _, text in target_items]
    matches: list[SimilarityMatch] = []

    docs: list[Path] = []
    if corpus_dir and corpus_dir.exists():
        docs.extend(path for path in corpus_dir.rglob("*.docx") if path.resolve() != target_docx.resolve())

    # Always include internal similarity as a baseline originality signal.
    internal_docs = [(target_docx.name, target_paragraphs)]
    external_docs: list[tuple[str, list[str]]] = []
    for doc in docs:
        try:
            external_docs.append((str(doc), [text for _, text in read_docx_paragraphs(doc)]))
        except Exception:
            continue

    for doc_name, source_paragraphs in [*internal_docs, *external_docs]:
        for target_index, target_text in enumerate(target_paragraphs, 1):
            for source_index, source_text in enumerate(source_paragraphs, 1):
                if doc_name == target_docx.name and abs(target_index - source_index) <= 1:
                    continue
                score = paragraph_similarity(target_text, source_text)
                if score >= min_similarity:
                    matches.append(
                        SimilarityMatch(
                            source_doc=doc_name,
                            source_paragraph=source_index,
                            target_paragraph=target_index,
                            similarity_pct=score,
                            target_excerpt=target_text[:320],
                            source_excerpt=source_text[:320],
                        )
                    )

    matches.sort(key=lambda item: item.similarity_pct, reverse=True)
    return matches[:max_matches]


def similarity_rows(matches: list[SimilarityMatch]) -> list[dict]:
    return [asdict(item) for item in matches]

