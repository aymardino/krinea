"""Open-access PDF lookup through Unpaywall (needs a contact e-mail, as their API asks)."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request


def fetch_pdf_by_doi(doi: str, email: str, dest_dir: str) -> str:
    """Try to download an open-access PDF for a DOI via Unpaywall.

    Returns the path to the saved PDF on success. Raises with a clear message
    when no OA copy is available or download fails — caller decides what to do
    (most common case: ask the user to upload the PDF manually).

    Note: only OA versions are fetched. Articles behind paywalls (much Elsevier
    content) won't be accessible this way — expect ~50-65% hit rate on energy
    journals.
    """
    doi = doi.strip().lower().replace("https://doi.org/", "").replace("doi.org/", "")
    if not doi or "/" not in doi:
        raise ValueError("Doesn't look like a valid DOI (expected '10.xxxx/yyyy').")

    api = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='/')}?email={urllib.parse.quote(email)}"
    req = urllib.request.Request(api, headers={"User-Agent": "Krinea/0.1 (research; https://github.com/aymardino/krinea)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        raise RuntimeError(f"Unpaywall lookup failed: {e}")

    if not data.get("is_oa"):
        raise FileNotFoundError(f"No open-access copy available for DOI {doi}. "
                                "You'll need to upload the PDF manually.")

    best = data.get("best_oa_location") or {}
    pdf_url = best.get("url_for_pdf") or best.get("url")
    if not pdf_url:
        raise FileNotFoundError(f"Unpaywall lists OA for {doi} but no PDF URL — upload manually.")

    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", doi) + ".pdf"
    out_path = os.path.join(dest_dir, safe_name)
    try:
        req2 = urllib.request.Request(pdf_url, headers={
            "User-Agent": "Mozilla/5.0 (research)",
            "Accept": "application/pdf,*/*"})
        with urllib.request.urlopen(req2, timeout=30) as resp:
            with open(out_path, "wb") as f:
                f.write(resp.read())
    except Exception as e:
        raise RuntimeError(f"Found OA URL but download failed ({pdf_url[:80]}…): {e}")
    return out_path

