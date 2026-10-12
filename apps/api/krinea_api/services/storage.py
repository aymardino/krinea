"""PDF storage: local folder in development, S3-compatible bucket in production.

Keys look like `<review_id>/<record_id>_<file name>`; in a bucket they live under `pdfs/`.
"""
from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Iterable
from pathlib import Path

from krinea_api.config import get_settings

log = logging.getLogger("krinea.storage")
_REVIEW_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
_S3_BATCH = 1000                          # most keys DeleteObjects accepts in one request


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "file.pdf")[:120]


def _local_root() -> Path:
    p = get_settings().data_dir / "pdfs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _local_path(key: str) -> Path | None:
    """Path of a key in the local folder, or None if the key would point outside it."""
    root = _local_root().resolve()
    path = (root / key).resolve()
    return path if root in path.parents else None


def _s3():
    import boto3
    s = get_settings()
    kw = {"region_name": s.s3_region}
    if s.s3_endpoint:
        kw["endpoint_url"] = s.s3_endpoint
    return boto3.client("s3", **kw)


def _s3_delete(client, bucket: str, full_keys: list[str]) -> None:
    """DeleteObjects in batches; falls back to one DeleteObject per key for S3-compatible
    services that reject the batch call. Failures are logged, never raised."""
    for i in range(0, len(full_keys), _S3_BATCH):
        batch = full_keys[i:i + _S3_BATCH]
        try:
            r = client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True})
            for err in r.get("Errors", []):
                log.error("could not delete %s from bucket %s: %s", err.get("Key"), bucket, err.get("Message"))
            continue
        except Exception:                 # noqa: BLE001
            log.warning("DeleteObjects failed on bucket %s; deleting one object at a time", bucket)
        for k in batch:
            try:
                client.delete_object(Bucket=bucket, Key=k)
            except Exception:             # noqa: BLE001
                log.exception("could not delete %s from bucket %s", k, bucket)


def save_pdf(review_id: str, record_id: int, data: bytes, filename: str = "") -> str:
    key = f"{review_id}/{record_id}_{_safe(filename or 'paper.pdf')}"
    s = get_settings()
    if s.s3_bucket:
        _s3().put_object(Bucket=s.s3_bucket, Key="pdfs/" + key, Body=data, ContentType="application/pdf")
    else:
        path = _local_path(key)
        if path is None:
            raise ValueError(f"Invalid PDF key: {key!r}")
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
    path = _local_path(key)
    return path.read_bytes() if path is not None and path.exists() else None


def delete_pdf(key: str) -> None:
    delete_pdfs([key])


def delete_pdfs(keys: Iterable[str]) -> None:
    """Remove stored PDFs. Missing files are ignored; storage errors are logged, not raised,
    because callers have already deleted the database rows that pointed to the files."""
    keys = sorted({k for k in keys if k})
    if not keys:
        return
    s = get_settings()
    if s.s3_bucket:
        try:
            _s3_delete(_s3(), s.s3_bucket, ["pdfs/" + k for k in keys])
        except Exception:                 # noqa: BLE001
            log.exception("could not delete %d PDF(s) from bucket %s", len(keys), s.s3_bucket)
        return
    for key in keys:
        path = _local_path(key)
        if path is None:
            log.warning("refusing to delete PDF key outside the storage folder: %r", key)
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            log.exception("could not delete PDF %s", path)


def delete_review_pdfs(review_id: str) -> None:
    """Remove every stored PDF of a review (everything under `<review_id>/`), local or S3."""
    if not _REVIEW_ID.fullmatch(review_id or ""):
        raise ValueError(f"Not a review id: {review_id!r}")      # never let an empty prefix through
    s = get_settings()
    if s.s3_bucket:
        prefix = f"pdfs/{review_id}/"
        try:
            client = _s3()
            keys = [o["Key"] for page in client.get_paginator("list_objects_v2").paginate(Bucket=s.s3_bucket, Prefix=prefix)
                    for o in page.get("Contents", [])]
            _s3_delete(client, s.s3_bucket, keys)
        except Exception:                 # noqa: BLE001
            log.exception("could not delete the PDFs under %s in bucket %s", prefix, s.s3_bucket)
        return
    folder = _local_path(review_id)
    if folder is not None and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


_OMITTED = "\n\n[... middle of paper omitted to fit context ...]\n\n"


def pdf_text(data: bytes, max_chars: int = 800_000) -> str:
    """Plain text of a PDF (PyMuPDF); keeps the head and the tail of very long papers."""
    import pymupdf
    doc = pymupdf.open(stream=data, filetype="pdf")
    raw = "".join(page.get_text() for page in doc)
    doc.close()
    text = "".join(c for c in raw if c >= " " or c in "\t\n\r")
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.70)
    tail = max(max_chars - head - len(_OMITTED), 0)
    return text[:head] + _OMITTED + (text[-tail:] if tail else "")      # text[-0:] would be all of it
