"""
screening.py — Screening logic shared by the app and the tests.

- consensus(): combine several reviewers' decisions into one record status
  (include / exclude / maybe / conflict / pending), Rayyan-style.
- highlight(): mark inclusion / exclusion keywords in an abstract.
- build_screening_prompt() + ai_screen(): optional AI pre-screening against the
  project's criteria, through krinea_core.llm.
"""
from __future__ import annotations

import html
import json
import re

DECISIONS = ("include", "maybe", "exclude")
STAGES = {"ta": "Title & abstract", "ft": "Full text"}

DEFAULT_EXCLUSION_REASONS = [
    "Wrong population / setting",
    "Wrong intervention / topic",
    "Wrong outcome",
    "Wrong study design",
    "Not a primary study (editorial, abstract only, review)",
    "Language",
    "Full text not available",
    "Duplicate",
    "Other",
]

DEFAULT_CRITERIA = {
    "question": "",
    "inclusion": "",
    "exclusion": "",
    "exclusion_reasons": list(DEFAULT_EXCLUSION_REASONS),
    "highlight_include": [],
    "highlight_exclude": [],
    "required_reviewers": 1,
}


def criteria_with_defaults(criteria: dict | None) -> dict:
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULT_CRITERIA.items()}
    for k, v in (criteria or {}).items():
        if v is not None:
            out[k] = v
    if not out.get("exclusion_reasons"):
        out["exclusion_reasons"] = list(DEFAULT_EXCLUSION_REASONS)
    try:
        out["required_reviewers"] = max(1, int(out.get("required_reviewers") or 1))
    except (TypeError, ValueError):
        out["required_reviewers"] = 1
    return out


def parse_keywords(text) -> list[str]:
    """'solar, mini-grid; Africa' -> ['solar', 'mini-grid', 'Africa']"""
    if isinstance(text, (list, tuple)):
        items = text
    else:
        items = re.split(r"[,;\n]", str(text or ""))
    seen, out = set(), []
    for it in items:
        it = str(it).strip()
        if it and it.lower() not in seen:
            seen.add(it.lower())
            out.append(it)
    return out


# ── Consensus between reviewers ──────────────────────────────────────────────────
def consensus(decisions: dict, required: int = 1) -> str:
    """decisions: {reviewer: 'include'|'maybe'|'exclude'}.

    A decision recorded under the reviewer name 'consensus' settles the record.
    Otherwise: fewer than `required` decisions -> pending; everyone agrees -> that
    decision; any 'maybe' alongside a single other value -> maybe; otherwise conflict.
    """
    if not decisions:
        return "pending"
    if "consensus" in decisions:
        return decisions["consensus"]
    values = [v for v in decisions.values() if v in DECISIONS]
    if not values:
        return "pending"
    if len(values) < max(1, required):
        return "pending"
    distinct = set(values)
    if len(distinct) == 1:
        return values[0]
    if "maybe" in distinct and len(distinct - {"maybe"}) == 1:
        return "maybe"
    return "conflict"


# ── Keyword highlighting ─────────────────────────────────────────────────────────
_INC_STYLE = "background:#CDE8D2;color:#1E5E3C;padding:0 2px;border-radius:3px;"
_EXC_STYLE = "background:#F4D3D3;color:#7A1F1F;padding:0 2px;border-radius:3px;"


def _kw_regex(kw: str) -> str:
    """'mini*grid' style wildcards, whole-word matching otherwise."""
    parts = [re.escape(p) for p in kw.split("*")]
    body = r"\w*".join(parts)
    return rf"\b{body}\b" if not kw.endswith("*") else rf"\b{body}"


def highlight(text: str, include_kw=(), exclude_kw=()) -> str:
    """Return HTML with inclusion keywords in green and exclusion keywords in red."""
    text = html.escape(str(text or ""))
    inc = [k for k in parse_keywords(include_kw) if k]
    exc = [k for k in parse_keywords(exclude_kw) if k]
    if not inc and not exc:
        return text
    inc_set = {k.lower() for k in inc}
    all_kw = sorted(set(inc + exc), key=len, reverse=True)
    pattern = re.compile("|".join(f"(?:{_kw_regex(k)})" for k in all_kw), re.I)

    def repl(m):
        word = m.group(0)
        is_inc = any(re.fullmatch(_kw_regex(k), word, re.I) for k in inc)
        style = _INC_STYLE if is_inc or word.lower() in inc_set else _EXC_STYLE
        return f"<mark style='{style}'>{word}</mark>"

    return pattern.sub(repl, text)


# ── AI pre-screening ─────────────────────────────────────────────────────────────
def record_text(record: dict) -> str:
    lines = [f"Title: {record.get('title', '')}"]
    meta = " · ".join(str(record.get(k) or "") for k in ("authors", "year", "journal")
                      if record.get(k))
    if meta:
        lines.append(meta)
    if record.get("keywords"):
        lines.append(f"Keywords: {record['keywords']}")
    lines.append(f"Abstract: {record.get('abstract') or '(no abstract available)'}")
    return "\n".join(lines)


def build_screening_prompt(criteria: dict, record: dict, stage: str = "ta",
                           full_text: str = "") -> str:
    c = criteria_with_defaults(criteria)
    reasons = " | ".join(c["exclusion_reasons"])
    what = ("its title and abstract" if stage == "ta" else "its full text")
    body = record_text(record)
    if stage == "ft" and full_text:
        body += "\n\nFULL TEXT:\n" + full_text
    return f"""You are assisting a systematic review. Decide whether the study below should be INCLUDED based on {what}, strictly applying the criteria. When the text does not give enough information to decide, answer "maybe": never exclude a study only because information is missing.

Research question: {c['question'] or '(not stated)'}

INCLUSION CRITERIA:
{c['inclusion'] or '(none stated)'}

EXCLUSION CRITERIA:
{c['exclusion'] or '(none stated)'}

If you exclude, pick the reason from this list only: {reasons}

Return ONLY a JSON object with exactly these keys:
{{"decision": "include" | "maybe" | "exclude",
 "reason": "<one of the exclusion reasons, or empty string>",
 "rationale": "<one or two sentences quoting the decisive evidence>",
 "confidence": <number between 0 and 1>}}

STUDY TEXT:
{body}

Return ONLY the JSON object, no markdown fences, no commentary."""


def parse_suggestion(raw) -> dict:
    """Normalise whatever the model returned into {decision, reason, rationale, confidence}."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    raw = raw if isinstance(raw, dict) else {}
    decision = str(raw.get("decision", "")).strip().lower()
    if decision not in DECISIONS:
        decision = "maybe"
    try:
        confidence = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = min(1.0, max(0.0, confidence))
    return {"decision": decision,
            "reason": str(raw.get("reason", "") or "").strip(),
            "rationale": str(raw.get("rationale", "") or "").strip(),
            "confidence": confidence}


def ai_screen(record: dict, criteria: dict, api_key: str, provider: str = "claude",
              model: str | None = None, stage: str = "ta", full_text: str = "") -> dict:
    """Ask the configured LLM for a screening suggestion. Never raises on bad JSON:
    an unparseable answer becomes a low-confidence 'maybe'."""
    from krinea_core import llm  # lazy: pulls in the provider SDKs only when actually used
    prompt = build_screening_prompt(criteria, record, stage=stage, full_text=full_text)
    try:
        raw, _usage = llm.call_json(prompt, provider, api_key, model, purpose="screening")
    except (json.JSONDecodeError, ValueError):
        raw = {}
    out = parse_suggestion(raw)
    out["model"] = model or provider
    return out
