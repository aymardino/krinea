"""Plain text out of a PDF (PyMuPDF), with head+tail truncation for very long papers."""
from __future__ import annotations

import threading
from contextlib import contextmanager

import pymupdf

# PyMuPDF must not be used from several threads at once, and MuPDF keeps the fonts and images
# of the documents it has read in a cache of up to 256 MB that it does not empty by itself. A
# server reads one PDF at a time and empties the cache after each (D-56).
_LOCK = threading.Lock()


@contextmanager
def reading():
    """Hold while a PDF is open: one PDF at a time, MuPDF's cache emptied after."""
    with _LOCK:
        try:
            yield
        finally:
            pymupdf.TOOLS.store_shrink(100)

_OMITTED = "\n\n[... middle of paper omitted to fit context ...]\n\n"


def extract_text(pdf_path: str, max_chars: int = 800_000) -> str:
    """Extract plain text from a PDF.

    For long papers (>max_chars), keep the FIRST ~70% and LAST ~30% of the
    character budget — abstracts/intro live at the start, but results, key
    findings and conclusions live at the end. Pure head-truncation loses them.
    """
    with reading():
        doc = pymupdf.open(pdf_path)
        try:
            raw = "".join(page.get_text() for page in doc)
        finally:
            doc.close()
    # Strip control characters that break HTML/DOM rendering downstream
    # (some PDFs embed them via OCR artefacts or broken encoding). Keep
    # normal whitespace (tab, newline, carriage return).
    text = "".join(c for c in raw if c >= " " or c in "\t\n\r")
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.70)
    tail = max(max_chars - head - len(_OMITTED), 0)
    return text[:head] + _OMITTED + (text[-tail:] if tail else "")      # text[-0:] would be all of it
