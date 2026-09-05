"""
anomalies.py — Flag suspicious or inconsistent values in an extraction draft.

Drop this file next to extraction_app.py and extractor.py.

Purpose: instead of re-reading all 34-52 fields on every study, you only look at
what the checker flags. Three severity levels:

    "error"   (red)    — internally inconsistent or invalid. Almost always wrong.
    "warning" (amber)  — plausible but worth a look. Often wrong in practice.
    None      (green)  — nothing detected. Skim it.

The checker is deliberately conservative: it flags things it can PROVE are odd
(a value outside its own vocabulary, a count that doesn't match, a date range
that runs backwards) plus a short list of patterns that have actually produced
wrong extractions in this project. It does not try to second-guess content it
cannot verify.
"""

import re
import datetime as _dt

import extractor


# ── Field-level rules ────────────────────────────────────────────────────────────

# Fields that should essentially never be empty on a verified study.
REQUIRED_FIELDS = {"full_title", "authors", "year", "extraction_level",
                   "scale", "countries", "nb_countries_covered",
                   "study_objective", "key_result", "tools_used",
                   "tool_categories", "study_category"}

# Fields usually derivable from any modelling paper — empty is possible but
# worth a second look before saving.
EXPECTED_FIELDS = {"model_name", "sector", "open_source", "aisesa_theme",
                   "author_origin", "authors_affiliation", "local_ownership",
                   "grey_literature", "link_doi", "contact", "approach", "method"}

# Tools that indicate a whole-system model. Used to sanity-check extraction_level.
WHOLE_SYSTEM_TOOLS = {"message", "messageix", "osemosys", "times", "tiam", "markal",
                      "leap", "plexos", "balmorel", "energyplan", "temba", "pypsa",
                      "calliope", "genx", "switch", "oemof", "urbs"}

# Words that signal a macroeconomic coupling -> approach should be "hybrid".
MACRO_COUPLING_CUES = {"cge", "computable general equilibrium", "macro", "e3me",
                       "gemini-e3", "gtem", "input-output", "economy-wide",
                       "macroeconomic feedback"}

# Organisations frequently mistaken for model users when they are only funders
# or acknowledged parties.
FUNDER_LIKE = {"european union", "european commission", "world bank", "usaid",
               "giz", "dfid", "fcdo", "sida", "norad", "afd", "undp", "unep"}

VALID_ISO2 = set(extractor.COUNTRY_POOL)


def _split(value):
    return [x.strip() for x in re.split(r"[,;]", str(value or "")) if x.strip()]


def _norm(value):
    return str(value or "").strip().lower()


def check_draft(values: dict, quotes: dict | None = None) -> dict:
    """Return {field_name: (severity, message)} for every field with a problem.

    values: {field: value} as shown in the verification form
    quotes: {field: source quote} — used to flag values with no textual support
    """
    quotes = quotes or {}
    flags = {}

    def flag(field, severity, message):
        # An error always overrides a warning on the same field
        if field in flags and flags[field][0] == "error":
            return
        flags[field] = (severity, message)

    field_spec = {n: (k, h) for n, k, h in extractor.FIELDS}
    level = _norm(values.get("extraction_level"))
    in_scope = set(extractor.fields_in_scope(level)) if level else set(values)

    # ── 1. Vocabulary and type validation, field by field ────────────────────
    for field, (kind, hint) in field_spec.items():
        if field not in in_scope:
            continue
        raw = values.get(field, "")
        val = _norm(raw)

        if not val:
            if field in REQUIRED_FIELDS:
                flag(field, "error", "Required field is empty")
            elif field in EXPECTED_FIELDS:
                flag(field, "warning", "Empty — check whether the paper states it")
            continue

        if kind == "enum" and val not in [_norm(o) for o in hint]:
            flag(field, "error", f"'{raw}' is not one of: {', '.join(hint)}")
        elif kind == "yesno" and val not in ("yes", "no"):
            flag(field, "error", f"'{raw}' should be yes or no")
        elif kind == "ynp" and val not in ("yes", "no", "partial"):
            flag(field, "error", f"'{raw}' should be yes, no or partial")
        elif kind == "year":
            if not re.fullmatch(r"\d{4}", val):
                flag(field, "error", f"'{raw}' is not a 4-digit year")
            elif not (1970 <= int(val) <= _dt.date.today().year + 40):
                flag(field, "warning", f"Year {raw} is outside the expected range")

        # A filled field with no supporting quote may be a model guess
        if field in in_scope and val and not str(quotes.get(field, "")).strip():
            if kind in ("enum", "yesno", "ynp") or field in REQUIRED_FIELDS:
                flag(field, "warning", "No source quote, check the text")

    # ── 2. Country consistency ───────────────────────────────────────────────
    countries = _split(values.get("countries"))
    bad_iso = [c for c in countries if c.upper() not in VALID_ISO2]
    if bad_iso:
        flag("countries", "error",
             f"Not valid African ISO-2 codes: {', '.join(bad_iso)}")

    declared = str(values.get("nb_countries_covered", "")).strip()
    if declared.isdigit() and countries:
        gap = int(declared) - len(countries)
        if gap > 0:
            flag("nb_countries_covered", "warning",
                 f"Declares {declared} countries but only {len(countries)} are listed")
        elif gap < 0:
            flag("nb_countries_covered", "error",
                 f"Declares {declared} but {len(countries)} countries are listed")

    scale = _norm(values.get("scale"))
    if scale == "national" and len(countries) > 1:
        flag("scale", "warning", f"Scale is 'national' but {len(countries)} countries listed")
    if scale in ("continental", "regional") and len(countries) == 1:
        flag("scale", "warning", f"Scale is '{scale}' but only one country listed")

    # ── 3. Tools and categories must align by position ───────────────────────
    tools = _split(values.get("tools_used"))
    cats = _split(values.get("tool_categories"))
    if tools and cats and len(tools) != len(cats):
        flag("tool_categories", "error",
             f"{len(tools)} tool(s) but {len(cats)} categor(y/ies) — must align by position")
    if not tools and level:
        flag("tools_used", "warning", "No tool recorded")

    # ── 4. extraction_level vs the tools actually used ───────────────────────
    tools_l = {_norm(t) for t in tools}
    has_ws = any(any(w in t for w in WHOLE_SYSTEM_TOOLS) for t in tools_l)
    if level == "full" and tools and not has_ws:
        flag("extraction_level", "warning",
             "Marked whole-system but no whole-system tool (MESSAGE, OSeMOSYS, "
             "TIMES, LEAP, PLEXOS…) is listed")
    if level == "light" and has_ws:
        flag("extraction_level", "warning",
             "Marked focused but a whole-system tool is listed")

    # ── 5. Time horizon ──────────────────────────────────────────────────────
    start = str(values.get("time_horizon_start", "")).strip()
    end = str(values.get("time_horizon_end", "")).strip()
    if start.isdigit() and end.isdigit() and int(end) < int(start):
        flag("time_horizon_end", "error", f"End year {end} is before start year {start}")

    year = str(values.get("year", "")).strip()
    if year.isdigit() and start.isdigit() and int(start) > int(year) + 5:
        flag("time_horizon_start", "warning",
             f"Horizon starts in {start}, well after publication year {year}")

    # ── 6. Approach vs macroeconomic coupling ────────────────────────────────
    approach = _norm(values.get("approach"))
    haystack = " ".join([_norm(values.get(f)) for f in
                         ("tools_used", "model_name", "study_objective", "key_result")])
    if approach == "bottom-up" and any(cue in haystack for cue in MACRO_COUPLING_CUES):
        flag("approach", "warning",
             "Macro-coupling cue found in the text — check whether this is hybrid")

    # ── 7. Style rules the prompt asks for ───────────────────────────────────
    obj = str(values.get("study_objective", "")).strip()
    if obj and not obj.lower().startswith("to "):
        flag("study_objective", "warning", "Should start with an infinitive ('To assess…')")
    for f in ("study_objective", "key_result"):
        v = str(values.get(f, "")).strip()
        if v and re.match(r"^(the authors|this (study|paper|article))", v.lower()):
            flag(f, "warning", "Starts with filler ('The authors…', 'This study…')")

    # ── 8. Authorship ────────────────────────────────────────────────────────
    authors = str(values.get("authors", "")).strip()
    if authors and authors.count(",") >= 2 and "et al" not in authors.lower():
        flag("authors", "warning", "Looks like a full author list — expected 'Lead et al.'")

    origins = _split(values.get("author_origin"))
    bad_origin = [c for c in origins if not re.fullmatch(r"[A-Za-z]{2}", c)]
    if bad_origin:
        flag("author_origin", "error", f"Not ISO-2 codes: {', '.join(bad_origin)}")

    local = _norm(values.get("local_ownership"))
    if local == "yes" and origins and not any(c.upper() in VALID_ISO2 for c in origins):
        flag("local_ownership", "warning",
             "Marked African-led but no African country in author_origin")

    # ── 9. Institutional users often confused with funders ───────────────────
    users = _split(values.get("institutional_users"))
    suspect = [u for u in users if _norm(u) in FUNDER_LIKE]
    if suspect:
        flag("institutional_users", "warning",
             f"May be funders/acknowledged rather than users: {', '.join(suspect)}")

    # ── 10. Cost of capital plausibility ─────────────────────────────────────
    coc = str(values.get("cost_of_capital", "")).strip()
    if coc and _norm(coc) != "not_stated":
        m = re.search(r"(\d+(?:\.\d+)?)", coc)
        if m:
            rate = float(m.group(1))
            if rate <= 1:
                flag("cost_of_capital", "warning",
                     f"'{coc}' — is this {rate*100:.0f}% written as a fraction?")
            elif rate > 30:
                flag("cost_of_capital", "warning", f"{rate}% is unusually high")

    # ── 11. grey_literature should agree with the document type ──────────────
    doi = str(values.get("link_doi", "")).strip()
    grey = _norm(values.get("grey_literature"))
    if grey == "no" and not doi:
        flag("grey_literature", "warning", "Marked peer-reviewed but no DOI recorded")

    return flags


def summarise(flags: dict) -> tuple[int, int]:
    """Return (n_errors, n_warnings) for a flags dict."""
    errors = sum(1 for s, _ in flags.values() if s == "error")
    warnings = sum(1 for s, _ in flags.values() if s == "warning")
    return errors, warnings
