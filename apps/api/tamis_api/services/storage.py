"""PDF storage: local folder in development, S3-compatible bucket in production."""
from __future__ import annotations

import re
from pathlib import Path

from tamis_api.config import get_settings


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "file.pdf")[:120]


def _local_root() -> Path:
    p = get_settings().data_dir / "pdfs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _s3():
    import boto3
    s = get_settings()
    kw = {"region_name": s.s3_region}
    if s.s3_endpoint:
        kw["endpoint_url"] = s.s3_endpoint
    return boto3.client("s3", **kw)


def save_pdf(review_id: str, record_id: int, data: bytes, filename: str = "") -> str:
    key = f"{review_id}/{record_id}_{_safe(filename or 'paper.pdf')}"
    s = get_settings()
    if s.s3_bucket:
        _s3().put_object(Bucket=s.s3_bucket, Key="pdfs/" + key, Body=data, ContentType="application/pdf")
    else:
        path = _local_root() / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return key


def read_pdf(key: str) -> bytes | None:
    if not key:
        return None
    s = get_settings()
    if s.s3_bucket:
        try:
            return _s3().get_object(Bucket=s.s3_bucket, Key="pdfs/" + key)["Body"].read()
        except Exception:                 # noqa: BLE001
            return None
    path = _local_root() / key
    return path.read_bytes() if path.exists() else None


def delete_pdf(key: str) -> None:
    if not key:
        return
    s = get_settings()
    if s.s3_bucket:
        try:
            _s3().delete_object(Bucket=s.s3_bucket, Key="pdfs/" + key)
        except Exception:                 # noqa: BLE001
            pass
    else:
        path = _local_root() / key
        if path.exists():
            path.unlink()


def pdf_text(data: bytes, max_chars: int = 800_000) -> str:
    """Plain text of a PDF (PyMuPDF); keeps the head and the tail of very long papers."""
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    raw = "".join(page.get_text() for page in doc)
    doc.close()
    text = "".join(c for c in raw if c >= " " or c in "\t\n\r")
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.70)
    return text[:head] + "\n\n[... middle of paper omitted to fit context ...]\n\n" + text[-(max_chars - head - 50):]
