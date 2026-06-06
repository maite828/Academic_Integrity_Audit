from __future__ import annotations

import re
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


SECTION_RE = re.compile(r"^(?:[0-9]+(?:\.[0-9]+)*\.?\s+|[IVX]+\.\s+).+")


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


def read_pdf_paragraphs(path: Path) -> list[tuple[str, str]]:
    """Return non-empty PDF text blocks as (section, text)."""
    if PdfReader is None:  # pragma: no cover
        raise RuntimeError("Missing dependency: pypdf. Install with: python -m pip install pypdf")

    reader = PdfReader(str(path))
    items: list[tuple[str, str]] = []
    section = "Front matter"

    for page_index, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        if not blocks:
            lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
            blocks = lines
        for block in blocks:
            paragraph = " ".join(block.split())
            if not paragraph:
                continue
            lower = paragraph.lower()
            if SECTION_RE.match(paragraph) or lower in {
                "resumen",
                "abstract",
                "referencias",
                "bibliografia",
                "bibliography",
            }:
                section = paragraph
            elif page_index > 1 and section == "Front matter":
                section = f"PDF page {page_index}"
            items.append((section, paragraph))
    return items


def read_document_paragraphs(path: Path) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx_paragraphs(path)
    if suffix == ".pdf":
        return read_pdf_paragraphs(path)
    raise ValueError(f"Unsupported document format: {path.suffix}. Use .docx or .pdf.")
