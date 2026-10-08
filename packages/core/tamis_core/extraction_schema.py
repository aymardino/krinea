"""
extraction_schema.py — Author-defined data extraction forms.

The review author decides which fields to extract (name, type, allowed values,
instruction for the AI). The schema lives in the project (JSON) and drives
three things: the AI prompt, the verification form and the export columns.

Field kinds:
    text       short free text                 number    a number (unit in the hint)
    sentences  one or two sentences            year      4-digit year
    yesno      yes | no                        enum      exactly one of `options`
    multi      one or more of `options`        list      free comma-separated list

    fields = extraction_schema.from_json(project["schema_json"])
    prompt = extraction_schema.build_prompt(fields, text, context=question)
    values, quotes = extraction_schema.clean_result(fields, llm_json)
    flags = extraction_schema.check_values(fields, values, quotes)
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import re

FIELD_KINDS = ["text", "sentences", "number", "year", "yesno", "enum", "multi", "list"]
KIND_LABELS = {
    "text": "Short text", "sentences": "Sentences (summary)", "number": "Number",
    "year": "Year", "yesno": "Yes / no", "enum": "Single choice", "multi": "Multiple choice",
    "list": "List (comma-separated)",
}

# A generic PICO-style starting point; the author edits or replaces it.
DEFAULT_SCHEMA = [
    {"name": "authors", "label": "Authors", "kind": "text", "options": [],
     "hint": "lead author followed by 'et al.' if more than two authors", "required": True},
    {"name": "year", "label": "Year", "kind": "year", "options": [], "hint": "", "required": True},
    {"name": "country", "label": "Country / setting", "kind": "list", "options": [],
     "hint": "countries or regions where the study took place", "required": True},
    {"name": "study_design", "label": "Study design", "kind": "enum",
     "options": ["experimental", "quasi-experimental", "observational", "modelling",
                 "qualitative", "review", "other"], "hint": "", "required": True},
    {"name": "population", "label": "Population", "kind": "sentences", "options": [],
     "hint": "who or what is studied", "required": False},
    {"name": "intervention", "label": "Intervention / exposure", "kind": "sentences",
     "options": [], "hint": "", "required": False},
    {"name": "comparator", "label": "Comparator", "kind": "text", "options": [],
     "hint": "", "required": False},
    {"name": "outcomes", "label": "Outcomes measured", "kind": "list", "options": [],
     "hint": "", "required": False},
    {"name": "sample_size", "label": "Sample size", "kind": "number", "options": [],
     "hint": "number of participants / units", "required": False},
    {"name": "key_result", "label": "Key result", "kind": "sentences", "options": [],
     "hint": "the main finding, directly, without 'The authors find that'", "required": True},
    {"name": "funding_declared", "label": "Funding declared", "kind": "yesno",
     "options": [], "hint": "", "required": False},
    {"name": "limitations", "label": "Limitations", "kind": "list", "options": [],
     "hint": "limitations acknowledged by the authors", "required": False},
]


def slugify(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(label or "").strip().lower()).strip("_")
    if not s:
        return "field"
    if s[0].isdigit():
        s = "f_" + s
    return s[:50]


def normalise_field(f: dict) -> dict:
    kind = str(f.get("kind", "text")).strip().lower()
    if kind not in FIELD_KINDS:
        kind = "text"
    opts = f.get("options", [])
    if isinstance(opts, str):
        opts = [o.strip() for o in re.split(r"[|;\n]", opts) if o.strip()]
    opts = [str(o).strip() for o in opts if str(o).strip()]
    label = str(f.get("label") or f.get("name") or "").strip()
    name = slugify(f.get("name") or label)
    required = f.get("required", False)
    if isinstance(required, str):
        required = required.strip().lower() in ("1", "true", "yes", "y", "oui")
    return {"name": name, "label": label or name.replace("_", " ").capitalize(),
            "kind": kind, "options": opts, "hint": str(f.get("hint", "") or "").strip(),
            "required": bool(required)}


def validate_schema(fields) -> list[str]:
    errors, seen = [], set()
    if not fields:
        errors.append("The schema has no field.")
    for i, f in enumerate(fields, 1):
        if f["name"] in seen:
            errors.append(f"Field {i}: name '{f['name']}' is used twice.")
        seen.add(f["name"])
        if f["kind"] in ("enum", "multi") and len(f["options"]) < 2:
            errors.append(f"Field '{f['name']}': {f['kind']} needs at least two options.")
    return errors


# ── Serialisation ────────────────────────────────────────────────────────────────
def to_json(fields) -> str:
    return json.dumps([normalise_field(f) for f in fields], ensure_ascii=False, indent=2)


def from_json(text) -> list[dict]:
    if not text:
        return [dict(f) for f in DEFAULT_SCHEMA]
    data = json.loads(text) if isinstance(text, str) else text
    if isinstance(data, dict):
        data = data.get("fields", [])
    return [normalise_field(f) for f in data if isinstance(f, dict)]


def to_csv(fields) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "label", "kind", "options", "hint", "required"])
    for f in fields:
        w.writerow([f["name"], f["label"], f["kind"], " | ".join(f["options"]),
                    f["hint"], "yes" if f["required"] else "no"])
    return buf.getvalue()


def from_csv(text: str) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    out = []
    for r in rows:
        r = {str(k).strip().lower(): (v or "") for k, v in r.items() if k}
        if not (r.get("name") or r.get("label")):
            continue
        out.append(normalise_field(r))
    return out


def energy_template() -> list[dict]:
    """The 52-field energy-modelling schema of extractor.py, as an importable example."""
    import extractor
    out = []
    for name, kind, hint in extractor.FIELDS:
        f = {"name": name, "label": name.replace("_", " ").capitalize(), "options": [], "hint": ""}
        if kind == "enum":
            f.update(kind="enum", options=list(hint))
        elif kind == "multi":
            f.update(kind="multi", options=list(hint))
        elif kind == "yesno":
            f.update(kind="yesno")
        elif kind == "ynp":
            f.update(kind="enum", options=["yes", "no", "partial"])
        elif kind == "year":
            f.update(kind="year", hint=hint)
        elif kind in ("iso", "list"):
            f.update(kind="list", hint=hint)
        elif kind == "sentences":
            f.update(kind="sentences", hint=hint)
        else:
            f.update(kind="text", hint=hint)
        out.append(normalise_field(f))
    return out


# ── Prompt ───────────────────────────────────────────────────────────────────────
def spec_line(f: dict) -> str:
    k, hint = f["kind"], f.get("hint", "")
    tail = f" — {hint}" if hint else ""
    if k == "enum":
        return f"- {f['name']}: choose ONE of: {' | '.join(f['options'])}{tail}"
    if k == "multi":
        return f"- {f['name']}: one or more (comma-separated) of: {' | '.join(f['options'])}{tail}"
    if k == "yesno":
        return f"- {f['name']}: yes | no{tail}"
    if k == "year":
        return f"- {f['name']}: 4-digit year{tail}"
    if k == "number":
        return f"- {f['name']}: a number (digits, decimal point allowed, no unit){tail}"
    if k == "list":
        return f"- {f['name']}: comma-separated list{tail}"
    if k == "sentences":
        return f"- {f['name']}: 1-2 short sentences{tail}"
    return f"- {f['name']}: short text{tail}"


def build_prompt(fields, text: str, context: str = "") -> str:
    specs = "\n".join(spec_line(f) for f in fields)
    ctx = f"\nContext of the review: {context.strip()}\n" if context and context.strip() else ""
    return f"""You are extracting structured data from a document for a systematic review.{ctx}
Extract ONLY what the text supports. If a field cannot be determined, use "" (empty string).

Return a SINGLE JSON object. For EVERY field below, return an object with:
  "value": the extracted value, respecting the allowed options EXACTLY (lowercase for options)
  "quote": a short verbatim snippet (< 25 words) from the text justifying it, or ""

FIELDS:
{specs}

STUDY TEXT:
{text}

Return ONLY the JSON object, no markdown fences, no commentary."""


def clean_result(fields, raw: dict) -> tuple[dict, dict]:
    """Split the model's {field: {value, quote}} answer into two flat dicts."""
    values, quotes = {}, {}
    raw = raw if isinstance(raw, dict) else {}
    for f in fields:
        item = raw.get(f["name"], "")
        if isinstance(item, dict):
            v, q = item.get("value", ""), item.get("quote", "")
        else:
            v, q = item, ""
        if isinstance(v, (list, tuple)):
            v = ", ".join(str(x) for x in v)
        v = " ".join(str(v if v is not None else "").split())
        if f["kind"] in ("enum", "multi", "yesno"):
            v = v.lower()
        values[f["name"]] = v
        quotes[f["name"]] = " ".join(str(q or "").split())
    return values, quotes


# ── Generic consistency checks (the anomalies.py idea, schema-driven) ────────────
def check_values(fields, values: dict, quotes: dict | None = None) -> dict:
    """{field: (severity, message)} — 'error' is invalid, 'warning' deserves a look."""
    quotes = quotes or {}
    flags = {}
    this_year = _dt.date.today().year
    for f in fields:
        name, kind = f["name"], f["kind"]
        val = str(values.get(name, "") or "").strip()
        if not val:
            if f.get("required"):
                flags[name] = ("error", "Required field is empty")
            continue
        low = val.lower()
        if kind == "enum" and low not in [o.lower() for o in f["options"]]:
            flags[name] = ("error", f"'{val}' is not one of: {', '.join(f['options'])}")
        elif kind == "multi":
            bad = [x.strip() for x in re.split(r"[,;]", val)
                   if x.strip() and x.strip().lower() not in [o.lower() for o in f["options"]]]
            if bad:
                flags[name] = ("error", f"Not allowed: {', '.join(bad)}")
        elif kind == "yesno" and low not in ("yes", "no"):
            flags[name] = ("error", f"'{val}' should be yes or no")
        elif kind == "year":
            if not re.fullmatch(r"\d{4}", val):
                flags[name] = ("error", f"'{val}' is not a 4-digit year")
            elif not (1900 <= int(val) <= this_year + 50):
                flags[name] = ("warning", f"Year {val} is outside the expected range")
        elif kind == "number":
            if not re.fullmatch(r"[-+]?\d[\d\s,]*(\.\d+)?", val):
                flags[name] = ("warning", f"'{val}' does not look like a plain number")
        if name not in flags and not str(quotes.get(name, "")).strip() \
                and (kind in ("enum", "yesno", "multi") or f.get("required")):
            flags[name] = ("warning", "No source quote, check the text")
    return flags


def summarise(flags: dict) -> tuple[int, int]:
    errors = sum(1 for s, _ in flags.values() if s == "error")
    return errors, len(flags) - errors


# ── Running an extraction ────────────────────────────────────────────────────────
def extract_pdf(fields, pdf_path: str, api_key: str, provider: str, model: str,
                context: str = "") -> tuple[dict, dict, str]:
    """PDF -> text -> LLM -> (values, quotes, text). Raises on unreadable PDFs."""
    import extractor
    text = extractor.extract_text(pdf_path)
    if len(text) < 500:
        raise ValueError("Extracted text too short — PDF may be scanned (needs OCR).")
    raw = extractor.call_llm(build_prompt(fields, text, context), api_key,
                             provider=provider, model=model)
    values, quotes = clean_result(fields, raw)
    return values, quotes, text
