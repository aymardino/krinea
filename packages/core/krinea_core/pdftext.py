"""Plain text out of a PDF (PyMuPDF), with head+tail truncation for very long papers."""
from __future__ import annotations

import fitz


def extract_text(pdf_path: str, max_chars: int = 800_000) -> str:
    """Extract plain text from a PDF.

    For long papers (>max_chars), keep the FIRST ~70% and LAST ~30% of the
    character budget — abstracts/intro live at the start, but results, key
    findings and conclusions live at the end. Pure head-truncation loses them.
    """
    doc = fitz.open(pdf_path)
    raw = "".join(page.get_text() for page in doc)
    # Strip control characters that break HTML/DOM rendering downstream
    # (some PDFs embed them via OCR artefacts or broken encoding). Keep
    # normal whitespace (tab, newline, carriage return).
    text = "".join(c for c in raw if c >= " " or c in "\t\n\r")
    doc.close()
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.70)
    tail = max_chars - head - 50  # 50 chars for the marker
    return text[:head] + "\n\n[... middle of paper omitted to fit context ...]\n\n" + text[-tail:]
