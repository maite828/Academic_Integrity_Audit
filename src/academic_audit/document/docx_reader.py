from __future__ import annotations

import re
import warnings
import logging
from pathlib import Path

try:
    from docx import Document
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: python-docx. Install with: python -m pip install python-docx"
    ) from exc

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


logging.getLogger("pypdf").setLevel(logging.ERROR)
SECTION_RE = re.compile(r"^(?:[0-9]+(?:\.[0-9]+)*\.?\s+|[IVX]+\.\s+).+")
PDF_SECTION_RE = re.compile(r"^(?:PREGUNTA\s+\d+|ANEXO\s+\d+|Tabla\s+\d+|Figura\s+\d+)\b", re.I)
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡0-9])")


def read_docx_paragraphs(path: Path) -> list[tuple[str, str]]:
    """Return non-empty paragraphs as (section, text)."""
    doc = Document(path)
    items: list[tuple[str, str]] = []
    section = "Front matter"

    for paragraph in doc.paragraphs:
        text = " ".join(paragraph.text.split())
        if not text:
            continue
        style = (paragraph.style.name or "").lower() if paragraph.style else ""
        lower = text.lower()
        if style.startswith("heading") or SECTION_RE.match(text) or lower in {
            "resumen",
            "abstract",
            "referencias",
            "bibliografia",
            "bibliography",
        }:
            section = text
        items.append((section, text))
    return items


def split_long_pdf_block(text: str, max_words: int = 180) -> list[str]:
    tokens = text.split()
    if len(tokens) <= max_words:
        return [text]

    sentences = [item.strip() for item in SENTENCE_BOUNDARY_RE.split(text) if item.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and current_words + sentence_words > max_words:
            chunks.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def normalize_pdf_blocks(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b(PREGUNTA\s+\d+)\b", r"\n\n\1", text, flags=re.I)
    text = re.sub(r"\b(ANEXO\s+\d+)\b", r"\n\n\1", text, flags=re.I)
    text = re.sub(r"\b(Tabla\s+\d+\.)", r"\n\n\1", text, flags=re.I)
    text = re.sub(r"\b(Figura\s+\d+\.)", r"\n\n\1", text, flags=re.I)
    text = re.sub(r"\s*[•●○]\s*", "\n\n", text)
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    split_blocks: list[str] = []
    for block in blocks:
        split_blocks.extend(split_long_pdf_block(block))
    return split_blocks


def pdf_section_title(paragraph: str, page_index: int, current: str) -> str:
    match = re.match(r"^(PREGUNTA\s+\d+)\b", paragraph, re.I)
    if match:
        return match.group(1).upper()
    match = re.match(r"^(ANEXO\s+\d+)\b", paragraph, re.I)
    if match:
        return match.group(1).upper()
    match = re.match(r"^(Tabla\s+\d+)", paragraph, re.I)
    if match:
        return match.group(1).capitalize()
    match = re.match(r"^(Figura\s+\d+)", paragraph, re.I)
    if match:
        return match.group(1).capitalize()
    if SECTION_RE.match(paragraph):
        return paragraph[:90]
    if page_index > 1 and current == "Front matter":
        return f"PDF page {page_index}"
    return current


def read_pdf_paragraphs(path: Path) -> list[tuple[str, str]]:
    """Return non-empty PDF text blocks as (section, text)."""
    if PdfReader is None:  # pragma: no cover
        raise RuntimeError("Missing dependency: pypdf. Install with: python -m pip install pypdf")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reader = PdfReader(str(path))
    items: list[tuple[str, str]] = []
    section = "Front matter"

    for page_index, page in enumerate(reader.pages, 1):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            text = page.extract_text() or ""
        blocks = normalize_pdf_blocks(text)
        for block in blocks:
            paragraph = " ".join(block.split())
            if not paragraph:
                continue
            lower = paragraph.lower()
            if SECTION_RE.match(paragraph) or PDF_SECTION_RE.match(paragraph) or lower in {
                "resumen",
                "abstract",
                "referencias",
                "bibliografia",
                "bibliography",
            }:
                section = pdf_section_title(paragraph, page_index, section)
            elif page_index > 1 and section == "Front matter":
                section = pdf_section_title(paragraph, page_index, section)
            items.append((section, paragraph))
    return items


def read_document_paragraphs(path: Path) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx_paragraphs(path)
    if suffix == ".pdf":
        return read_pdf_paragraphs(path)
    raise ValueError(f"Unsupported document format: {path.suffix}. Use .docx or .pdf.")
