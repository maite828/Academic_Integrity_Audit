from __future__ import annotations

import re
from pathlib import Path

try:
    from docx import Document
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: python-docx. Install with: python -m pip install python-docx"
    ) from exc


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

