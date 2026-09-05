"""
extractor.py — Core AI extraction for the AISESA observatory.

Pipeline: PDF -> text (PyMuPDF) -> Gemini structured JSON -> your full schema,
with a source quote for every field. Power pools are COMPUTED from the extracted
countries (deterministic), never guessed by the AI.

Usage:
    export GEMINI_API_KEY=...
    python extractor.py path/to/article.pdf

Dependencies: pip install pymupdf google-generativeai
"""

import os
import json
import re
import fitz  # PyMuPDF
import anthropic  # Claude API


# ── Country -> power pool map (from your database; authoritative) ────────────────
COUNTRY_POOL = {
    "CF": "CAPP", "CG": "CAPP", "CM": "CAPP", "GA": "CAPP", "GQ": "CAPP", "ST": "CAPP", "TD": "CAPP",
    "DZ": "COMELEC", "LY": "COMELEC", "MA": "COMELEC", "MR": "COMELEC", "TN": "COMELEC",
    "BI": "EAPP", "DJ": "EAPP", "EG": "EAPP", "ER": "EAPP", "ET": "EAPP", "KE": "EAPP", "KM": "EAPP",
    "MG": "EAPP", "MU": "EAPP", "RW": "EAPP", "SC": "EAPP", "SD": "EAPP", "SO": "EAPP", "SS": "EAPP",
    "TZ": "EAPP", "UG": "EAPP",
    "AO": "SAPP", "BW": "SAPP", "CD": "SAPP", "LS": "SAPP", "MW": "SAPP", "MZ": "SAPP", "NA": "SAPP",
    "SZ": "SAPP", "ZA": "SAPP", "ZM": "SAPP", "ZW": "SAPP",
    "BF": "WAPP", "BJ": "WAPP", "CI": "WAPP", "CV": "WAPP", "GH": "WAPP", "GM": "WAPP", "GN": "WAPP",
    "GW": "WAPP", "LR": "WAPP", "ML": "WAPP", "NE": "WAPP", "NG": "WAPP", "SL": "WAPP", "SN": "WAPP",
    "TG": "WAPP",
}
ISO_CODES = sorted(COUNTRY_POOL.keys())


def compute_pools(countries_csv: str) -> str:
    """Derive power pools from a comma-separated ISO-2 country string. Deterministic."""
    isos = [c.strip().upper() for c in re.split(r"[,;]", countries_csv) if c.strip()]
    pools = []
    for iso in isos:
        p = COUNTRY_POOL.get(iso)
        if p and p not in pools:
            pools.append(p)
    return ", ".join(pools)


# ── Field definitions: (name, kind, allowed_values_or_hint) ──────────────────────
# kind: "enum" (one value), "multi" (comma-list from set), "yesno", "ynp" (yes/no/partial),
#       "iso" (ISO-2 list), "text", "year", "sentences", "list"
FIELDS = [
    ("authors", "text", "author names"),
    ("model_name", "text", "primary named model/tool, or '' if custom/unnamed"),
    ("full_title", "text", "the paper's full title"),
    ("year", "year", ""), 
    ("tools_used", "list", "list ALL energy-modelling (ESM) tools used, comma-separated (e.g. "
        "MESSAGE, HOMER). STRICT RULES: "
        "(1) Only list dedicated energy-system-modelling software, NOT general-purpose languages "
        "or environments used to implement a custom model (exclude Excel, Python, MATLAB, R, Julia, "
        "GAMS-as-language). If the study builds its own model from scratch in "
        "one of these, with no identifiable ESM tool, write exactly 'none' if there are not energy modeling tools (this flags the study "
        "for exclusion from the inventory). Leave the field EMPTY only when you genuinely cannot "
        "determine what was used. "
        "(2) Do NOT list datasets (e.g. WorldPop, VIIRS night-lights, ERA5) as tools, those belong "
        "in other fields, not here. "
        "(3) Do NOT list methodologies or frameworks that are not standalone software (e.g. "
        "'multi-criteria analysis', 'linear programming') as tools. "
        "(4) Normalise names to their canonical short form, dropping edition/version suffixes: "
        "'HOMER Pro' becomes 'HOMER'; 'HOMER Grid' becomes 'HOMER'; 'ArcMap' becomes 'ArcGIS'; "
        "'ArcGIS Pro' becomes 'ArcGIS'; drop version numbers entirely (e.g. 'PVSyst 3.1' "
        "becomes 'PVSyst'). "
        "This uniform naming is critical: the same tool must always be written identically across "
        "every study so usage can be aggregated."),
    ("tool_categories", "list", "for EACH tool above, its category in the same order, comma-separated. "
        "Categories: capacity_expansion;production_cost;geospatial_electrification;reliability;"
        "nexus;demand_forecast;system_dynamics;hybrid_optimization"),
    ("extraction_level", "enum", ["full", "light"]),
    ("study_category", "enum", ["long_term_planning", "rural_electrification", "microgrid",
        "dispatch", "nexus", "economic", "geospatial"]),
    ("scale", "enum", ["national", "subnational", "regional", "continental", "global"]),
    ("countries", "iso", "comma-separated ISO-2 codes of ALL countries studied"),
    ("nb_countries_covered", "text", "number of countries covered (integer)"),
    ("study_objective", "sentences", "1-2 sentences on the study's objective"),
    ("key_result", "sentences", "1-2 sentences on the key result"),
    ("time_horizon_start", "year", "first year of the modelling horizon, ONLY if explicitly "
    "stated as a calendar year in the text. Do NOT use the publication year. Do NOT compute "
    "it from a stated project lifetime (e.g. '20 year lifetime' does NOT mean start=publication "
    "year). If no explicit start year is stated, leave blank."),
    ("time_horizon_end", "year", "last year of the modelling horizon, ONLY if explicitly "
    "stated as a calendar year in the text. Do NOT use the publication year. Do NOT compute "
    "it from a stated project lifetime (e.g. '20-year lifetime' does NOT mean end=publication "
    "year). If no explicit end year is stated, leave blank."),
    ("approach", "enum", ["bottom-up", "top-down", "hybrid"]),
    ("method", "enum", ["optimization", "simulation", "accounting", "hybrid"]),
    ("mathematical_approach", "enum", ["linear_programming", "mixed-integer_programming",
        "dynamic_programming", "stochastic", "other"]),
    ("hydro", "yesno", ""), ("solar", "yesno", ""), ("wind", "yesno", ""),
    ("biomass", "yesno", ""), ("nuclear", "yesno", ""), ("geothermal", "yesno", ""),
    ("fossil", "yesno", ""), ("h2", "yesno", ""), ("coal", "yesno", ""),
    ("sector", "enum", ["electricity", "full_energy", "power_heat", "other"]),
    ("open_source", "enum", ["open", "proprietary", "mixed"]),
    ("sdg_7", "yesno", ""), ("sdg_13", "yesno", ""),
    ("ndc_mention", "yesno", ""), ("agenda_2063", "yesno", ""),
    ("aisesa_theme", "enum", ["powering_livelihoods", "inclusive_industrialisation",
        "urban_transitions", "cross_cutting", "none"]),
    ("informal_economy", "ynp", ""), ("biomass_charcoal", "ynp", ""),
    ("clean_cooking", "ynp", ""), ("power_reliability", "ynp", ""), ("urbanization", "ynp", ""),
    ("strengths", "list", "strengths mentioned in the article, words/phrases comma-separated"),
    ("weaknesses", "list", "weaknesses mentioned, words/phrases comma-separated"),
    ("authors_affiliation", "list", "author institutions, comma-separated"),
    ("author_origin", "iso", "ISO-2 codes of the authors' institutional countries"),
    ("local_ownership", "ynp", "yes if African-led institutions"),
    ("institutional_users", "list", "institutions that use this model/study, comma-separated"),
    ("grey_literature", "yesno", "yes if NDC, World Bank report, or non-peer-reviewed"),
    ("cost_of_capital", "text", "discount rate / WACC e.g. '8%' or 'not_stated'"),
    ("financing_modelling", "yesno", "does it model financing?"),
    ("financing_mechanism", "text", "financing mechanism described, or '' "),
    ("link_doi", "text", "the complete DOI URL, always starting with 'https://doi.org/' or "
        "'http://dx.doi.org/', never just the bare DOI text (e.g. write "
        "'https://doi.org/10.1016/j.rser.2020.110399', not '10.1016/j.rser.2020.110399'). "
        "If no DOI exists, use the article's full URL instead, also starting with http:// or https://."),
    ("contact", "text", "corresponding author email if present"),
]

# Fields the model fills (everything except computed power_pool).
SCHEMA_FIELDS = [f[0] for f in FIELDS]
# Final export order adds the computed power_pool after countries.
EXPORT_FIELDS = []
for f in SCHEMA_FIELDS:
    EXPORT_FIELDS.append(f)
    if f == "nb_countries_covered":
        EXPORT_FIELDS.append("power_pool")

MODEL = "gemini-2.5-flash"


# ── Field scope per extraction_level ─────────────────────────────────────────────
# Gemini still extracts everything (one API call, deterministic). But the
# verification form and Excel export only show/keep the fields below per level.

FIELDS_BY_LEVEL = {
    "full": None,   # None = all SCHEMA_FIELDS + power_pool (52 fields total)
    "light": ["authors", "model_name", "full_title", "year", "extraction_level",
        "study_category", "tools_used", "tool_categories", "scale", "countries",
        "nb_countries_covered", "power_pool", "study_objective", "key_result", "sector",
        "open_source", "aisesa_theme", "informal_economy", "biomass_charcoal",
        "clean_cooking", "power_reliability", "urbanization", "link_doi", "contact",
        "sdg_7", "sdg_13", "ndc_mention", "time_horizon_start", "time_horizon_end",
        "authors_affiliation", "author_origin", "local_ownership", "grey_literature"],
}


def fields_in_scope(extraction_level: str) -> list:
    """Return the list of fields to keep for a given extraction level.
    Unknown / empty level → keep all fields (safe default)."""
    scope = FIELDS_BY_LEVEL.get(extraction_level)
    if scope is None:
        # 'full' or unknown → keep everything in EXPORT_FIELDS order
        return list(EXPORT_FIELDS)
    # Preserve EXPORT_FIELDS order for the scoped subset
    return [f for f in EXPORT_FIELDS if f in scope]


def _field_spec_line(name, kind, hint):
    if kind == "enum":
        return f"- {name}: choose ONE of: {' | '.join(hint)}"
    if kind == "multi":
        return f"- {name}: one or more (comma-separated) of: {' | '.join(hint)}"
    if kind == "yesno":
        return f"- {name}: yes | no"
    if kind == "ynp":
        return f"- {name}: yes | no | partial{(' — ' + hint) if hint else ''}"
    if kind == "iso":
        return f"- {name}: {hint}"
    if kind == "year":
        return f"- {name}: 4-digit year{(' — ' + hint) if hint else ''}"
    return f"- {name}: {hint}"


def extract_text(pdf_path: str, max_chars: int = 180_000) -> str:
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


def build_prompt(text: str) -> str:
    specs = "\n".join(_field_spec_line(n, k, h) for n, k, h in FIELDS)
    return f"""You are extracting structured data from an energy-modelling study for a systematic review of energy models applied in Africa. Extract ONLY what the text supports. If a field cannot be determined, use "" (empty string).

Return a SINGLE JSON object. For EVERY field below, return an object with:
  "value": the extracted value, respecting the allowed options EXACTLY (lowercase)
  "quote": a short verbatim snippet (< 25 words) from the text justifying it, or ""

KEY GUIDANCE:

extraction_level: classify by the TYPE OF MODEL used in the study.

  - "full" = long-term planning models: MESSAGE, OSeMOSYS, TIMES, LEAP, PLEXOS, Balmorel, etc...
    These include both long term optimization models and simulation/accounting models.
    This applies whether the document is a peer-reviewed article, a technical report,
    OR a country-policy document (NDC, national plan, World Bank report) that uses one
    of these tools. What matters is the model, not the document type.
    Examples: "Ghana NDC using LEAP" -> full. "IRENA West Africa study with OSeMOSYS" -> full. "Ghana energy transition study with EnergyPLAN" -> full.

  - "light" = everything else: techno-economic studies, GIS-based analyses, mini-grid
    simulations, rural electrification studies, calculators (GACMO, CERC, KCERT, 2050 Calculator), custom code. Also: country-policy documents that don't use a full long-term planning model.
    Examples: "HOMER mini-grid study" -> light. "Burkina Faso NDC using GACMO" -> light.
    "Ghana Energy Sector Review (World Bank)" -> light. "OnSSET electrification study" -> light.

  The `grey_literature` field (yes/no) captures whether the document is grey lit or
  peer-reviewed, which is a separate dimension.

countries: list EVERY country actually modelled, as ISO-2 codes, from this list ONLY:
  {", ".join(ISO_CODES)}. If the study is continental/regional, list all the specific countries you can identify.

tools_used and tool_categories MUST align by position (1st tool -> 1st category).
Read the article to determine HOW each tool is actually used in this specific study,
rather than assigning a default category based on the tool's name. The same tool can
serve different purposes in different studies (e.g. PLEXOS used for demand forecast in
one study, production cost simulation in another).

Do NOT output power pools — they are computed separately from the countries.

open_source: use the tool's KNOWN licence rather than waiting for the paper to say it. If the paper uses one of these tools, classify accordingly:
  - OPEN: every required component is free or open-source. The model can be installed and run end-to-end at zero cost.
    OSeMOSYS, OnSSET, GenX, PyPSA, Calliope, SWITCH, urbs, oemof, Balmorel, TEMBA, atlite, SAM, OSeR, Python/R custom code
  - PROPRIETARY: the tool itself requires a paid licence.
    LEAP (freemium, treat as proprietary), MESSAGE (IAEA, treat as proprietary), PLEXOS, ANTARES, HOMER Pro, Aurora, EnergyPLAN, PVsyst
  - MIXED: studies that combine an open tool with a proprietary one (e.g. MESSAGE + HOMER, OnSSET + LEAP) or 
    if the model code is free or open, but a commercial component is indispensable like TIMES which requires VEDA license and GAMS, or MARKAL, or BALMOREL.
  Only use "" if no specific tool can be identified.

approach: infer from the model structure even if the words are absent.
  - bottom-up: technology-rich models with technology-by-technology cost optimisation,
    and NO macroeconomic feedback module.
  - top-down: econometric, CGE, input-output or macro-economic models that start from
    aggregates without explicit technology detail.
  - hybrid: combines bottom-up technology detail WITH a top-down economic module.
    IMPORTANT: check for coupling before answering bottom-up. A study is hybrid whenever
    a technology-rich model is soft- or hard-linked to a macroeconomic model. Common
    hybrid cases: TIMES-MACRO, MESSAGE-MACRO, MESSAGEix-GLOBIOM, LEAP coupled with a
    CGE, OSeMOSYS linked to an economy-wide model, any "X + CGE" or "X + input-output"
    combination.
    Cue words that signal hybrid: "CGE", "computable general equilibrium", "MACRO module",
    "soft-linked", "hard-linked", "coupled with", "macroeconomic feedback",
    "input-output", "economy-wide".
  If the paper names two tools where one is technology-rich and the other is
  macroeconomic, answer "hybrid", not the category of the first tool.

mathematical_approach: infer from the method description.
  - linear_programming: LP, cost minimisation over continuous variables.
  - mixed-integer_programming: MILP, integer or binary decisions (unit commitment, plant build).
  - dynamic_programming: recursive optimisation over time stages.
  - stochastic: explicit uncertainty / scenario trees / probabilistic constraints.
  - other: simulation, multi-criteria, heuristics, agent-based.
  If the paper says "optimization" without detail, "linear_programming" is the safe default for cost-minimisation models like MESSAGE/OSeMOSYS/TIMES. Use "" only if truly indeterminable.

aisesa_theme: classify by which AISESA theme the study primarily addresses.
  - powering_livelihoods: productive uses of energy, rural electrification, energy access for households and small businesses.
  - inclusive_industrialisation: energy for industry, large-scale productive sectors, manufacturing.
  - urban_transitions: cities, urban energy planning, urban-rural dynamics.
  - cross_cutting: covers multiple themes or is a generic national-system study.
  - none: not aligned with any (rare).
  Most national planning studies = cross_cutting. Rural / off-grid / mini-grid studies = powering_livelihoods.

financing_modelling: be precise about the distinction.
  - "yes" ONLY IF the model EXPLICITLY represents financing variables (cost of capital differentiated by technology/country, debt-equity ratio, subsidies as model inputs, grant vs loan, ROI/IRR/NPV computed inside the model).
  - "no" if the paper merely mentions financing in the discussion, or uses a uniform discount rate without modelling financing structures.

financing_mechanism: name the mechanism IF financing_modelling is yes (e.g. "feed-in tariff", "concessional loan", "investment subsidy with 50% WACC reduction"). Leave "" otherwise.

study_objective: write 1-2 SHORT sentences synthesising the goal of the study, in your own words. START DIRECTLY WITH AN INFINITIVE VERB ("To assess...", "To compare...", "To model..."). Do NOT start with "The authors", "This study", "This paper" — that's verbose. Example: "To assess the cost of universal electrification in Burkina Faso under three scenarios." NOT "This study assesses..."

key_result: 1-2 SHORT sentences on the MAIN finding (not the methodology). Same style — direct, no "The authors find that..." padding. Example: "Decentralised PV mini-grids serve 60% of the off-grid population at lowest cost." NOT "The authors find that..."

authors: cite ONLY the lead author followed by "et al." if there are more than 2 authors. Examples:
  - one author: "M Moner-Girona"
  - two authors: "M Moner-Girona and J Doe"
  - multiple: "M Moner-Girona et al."
  Do NOT list all authors.

institutional_users: list organisations that ACTUALLY USE this model/study for their own work (e.g. "ECOWAS uses MESSAGE for power pool planning"). Do NOT list organisations merely acknowledged, thanked, cited as data providers, or funders. If the paper doesn't explicitly mention an organisation using the model, leave EMPTY.

FIELDS:
{specs}

STUDY TEXT:
{text}

Return ONLY the JSON object, no markdown fences, no commentary."""


def _try_parse_json(raw: str) -> dict:
    """Parse Gemini JSON output, with fallback strategies for malformed JSON."""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    # Strategy 1: straight parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Strategy 2: escape unescaped newlines inside string values (frequent culprit)
    fixed = re.sub(r'(?<!\\)\n(?=[^"]*"[^"]*$)', r'\\n', raw)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    # Strategy 3: trim everything before first { and after last }
    a, b = raw.find("{"), raw.rfind("}")
    if a != -1 and b != -1:
        try:
            return json.loads(raw[a:b+1])
        except json.JSONDecodeError:
            pass
    # Strategy 4: response truncated mid-generation (output token cap) — salvage
    # every complete top-level entry and close the object. Missing trailing
    # fields stay empty and get flagged by the anomaly checker instead of
    # losing the whole extraction.
    a = raw.find("{")
    if a != -1:
        closers = list(re.finditer(r"\}", raw))
        for m in reversed(closers[-200:]):
            candidate = raw[a:m.end()].rstrip().rstrip(",") + "}"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    # All strategies failed — raise the original error so caller sees it
    return json.loads(raw)


def call_gemini(prompt: str, api_key: str, model: str = MODEL, max_retries: int = 2) -> dict:
    """Call Gemini and parse the JSON response, with retry on malformed JSON."""
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gm = genai.GenerativeModel(model)
    last_raw = ""
    last_err = None
    for attempt in range(max_retries + 1):
        resp = gm.generate_content(
            prompt,
            generation_config={"temperature": 0, "response_mime_type": "application/json",
                               "max_output_tokens": 65536},
        )
        last_raw = resp.text or ""
        try:
            return _try_parse_json(last_raw)
        except json.JSONDecodeError as e:
            last_err = e
            if attempt < max_retries:
                continue
    debug_path = os.path.join(os.path.dirname(__file__) if "__file__" in globals() else ".",
                              "_last_bad_response.txt")
    try:
        with open(debug_path, "w", encoding="utf-8") as fh:
            fh.write(last_raw)
    except OSError:
        pass
    raise json.JSONDecodeError(
        f"{last_err.msg} (after {max_retries+1} attempts; raw response saved to "
        f"{debug_path} for inspection)", last_raw, last_err.pos)


def call_deepseek(prompt: str, api_key: str, model: str = "deepseek-v4-flash",
                  max_retries: int = 2) -> dict:
    """Call DeepSeek (OpenAI-compatible API) and parse the JSON response.

    DeepSeek's prompt caching kicks in automatically when the same system prompt
    is sent repeatedly — so batch extractions get progressively cheaper.
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    last_raw = ""
    last_err = None
    for attempt in range(max_retries + 1):
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        last_raw = resp.choices[0].message.content or ""
        try:
            return _try_parse_json(last_raw)
        except json.JSONDecodeError as e:
            last_err = e
            if attempt < max_retries:
                continue
    debug_path = os.path.join(os.path.dirname(__file__) if "__file__" in globals() else ".",
                              "_last_bad_response.txt")
    try:
        with open(debug_path, "w", encoding="utf-8") as fh:
            fh.write(last_raw)
    except OSError:
        pass
    raise json.JSONDecodeError(
        f"{last_err.msg} (after {max_retries+1} attempts; raw response saved to "
        f"{debug_path} for inspection)", last_raw, last_err.pos)

def call_claude(prompt: str, api_key: str, model: str = "claude-sonnet-5",
                max_retries: int = 2) -> dict:
    """Call Claude via Anthropic API and parse JSON. Uses prompt caching
    automatically on the system message — cached prompts cost 90% less after
    the first call, which matters when running 100+ extractions with the
    same instructions."""
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    last_raw = ""
    last_err = None

    # Split the prompt so the STABLE part (instructions, vocabularies) is cached,
    # and only the article text varies between calls.
    marker = "STUDY TEXT:"
    if marker in prompt:
        system_prompt, article = prompt.split(marker, 1)
        article = marker + article
    else:
        system_prompt, article = prompt, ""

    for attempt in range(max_retries + 1):
        resp = client.messages.create(
            model=model,
            max_tokens=8192,
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": article or prompt}],
        )
        # Claude returns a list of content blocks
        last_raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
        try:
            return _try_parse_json(last_raw)
        except json.JSONDecodeError as e:
            last_err = e
            if attempt < max_retries:
                continue
    debug_path = os.path.join(os.path.dirname(__file__) if "__file__" in globals() else ".",
                              "_last_bad_response.txt")
    try:
        with open(debug_path, "w", encoding="utf-8") as fh:
            fh.write(last_raw)
    except OSError:
        pass
    raise json.JSONDecodeError(
        f"{last_err.msg} (after {max_retries+1} attempts; raw response saved to "
        f"{debug_path} for inspection)", last_raw, last_err.pos)

def call_llm(prompt: str, api_key: str, provider: str = "gemini",
             model: str = None) -> dict:
    """Dispatch to the right provider. Use this instead of call_gemini directly."""
    if provider == "gemini":
        return call_gemini(prompt, api_key, model or "gemini-2.5-flash")
    elif provider == "deepseek":
        return call_deepseek(prompt, api_key, model or "deepseek-v4-flash")
    elif provider == "claude":
        return call_claude(prompt, api_key, model or "claude-sonnet-5")
    else:
        raise ValueError(f"Unknown provider: {provider!r} (use 'gemini' or 'deepseek' or 'claude')")


def upgrade_synthesis_fields(text: str, current: dict, api_key: str,
                              provider: str = "gemini") -> dict:
    """Re-run study_objective and key_result on the provider's 'pro' model
    (better at synthesis). Cheap: one short focused call per study.
    """
    prompt = f"""Read this energy-modelling study and write TWO short answers in your own words.

STYLE RULES (very important):
- study_objective: 1-2 short sentences, MUST START WITH AN INFINITIVE VERB ("To assess...",
  "To compare...", "To model..."). Do NOT start with "The authors", "This study", "This paper".
  Example: "To compare grid extension and decentralised PV options for rural Burkina Faso."
- key_result: 1-2 short sentences on the MAIN FINDING. Direct, no "The authors find that..."
  padding. Example: "Decentralised PV mini-grids serve 60% of off-grid population at lowest cost."

Return JSON: {{"study_objective": {{"value": "...", "quote": "short verbatim from text"}}, "key_result": {{"value": "...", "quote": "short verbatim"}}}}

STUDY TEXT:
{text}"""
    pro_model = "gemini-2.5-pro" if provider == "gemini" else "deepseek-v4-pro" if provider == "deepseek" else "claude-opus-5"
    upgraded = call_llm(prompt, api_key, provider=provider, model=pro_model)
    for f in ("study_objective", "key_result"):
        if f in upgraded and isinstance(upgraded[f], dict):
            current[f] = {"value": str(upgraded[f].get("value", "")).strip(),
                          "quote": str(upgraded[f].get("quote", "")).strip()}
    return current


def extract_pdf(pdf_path: str, api_key: str, model: str = MODEL,
                upgrade_synthesis: bool = False,
                provider: str = "gemini") -> dict:
    text = extract_text(pdf_path)
    if len(text) < 500:
        raise ValueError("Extracted text too short — PDF may be scanned (needs OCR).")
    result = call_llm(build_prompt(text), api_key, provider=provider, model=model)
    clean = {}
    for f in SCHEMA_FIELDS:
        item = result.get(f, {})
        if isinstance(item, dict):
            clean[f] = {"value": str(item.get("value", "")).strip(),
                        "quote": str(item.get("quote", "")).strip()}
        else:
            clean[f] = {"value": str(item).strip(), "quote": ""}
    # Optional upgrade: re-do the two synthesis fields with Pro
    pro_models = {"gemini-2.5-pro", "deepseek-v4-pro", "claude-opus-5"}
    if upgrade_synthesis and model not in pro_models:
        try:
            clean = upgrade_synthesis_fields(text, clean, api_key, provider=provider)
        except Exception as e:
            # Don't fail the whole extraction if the upgrade call fails
            print(f"[warn] synthesis upgrade failed, keeping Flash output: {e}")
    # Compute power pools from countries (deterministic, not AI-guessed)
    pools = compute_pools(clean.get("countries", {}).get("value", ""))
    clean["power_pool"] = {"value": pools, "quote": "computed from countries"}
    clean["_meta"] = {"source_file": os.path.basename(pdf_path),
                      "provider": provider, "model": model,
                      "synthesis_upgraded": upgrade_synthesis,
                      "text_chars": len(text)}
    return clean


def fetch_pdf_by_doi(doi: str, email: str, dest_dir: str) -> str:
    """Try to download an open-access PDF for a DOI via Unpaywall.

    Returns the path to the saved PDF on success. Raises with a clear message
    when no OA copy is available or download fails — caller decides what to do
    (most common case: ask the user to upload the PDF manually).

    Note: only OA versions are fetched. Articles behind paywalls (much Elsevier
    content) won't be accessible this way — expect ~50-65% hit rate on energy
    journals.
    """
    import urllib.request, urllib.parse
    doi = doi.strip().lower().replace("https://doi.org/", "").replace("doi.org/", "")
    if not doi or "/" not in doi:
        raise ValueError("Doesn't look like a valid DOI (expected '10.xxxx/yyyy').")

    api = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='/')}?email={email}"
    req = urllib.request.Request(api, headers={"User-Agent": "AISESA-extractor/1.0"})
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


if __name__ == "__main__":
    import sys
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("Set GEMINI_API_KEY environment variable first.")
    if len(sys.argv) < 2:
        sys.exit("Usage: python extractor.py path/to/article.pdf")
    data = extract_pdf(sys.argv[1], key)
    for f in EXPORT_FIELDS:
        v = data.get(f, {}).get("value", "")
        q = data.get(f, {}).get("quote", "")
        print(f"{f:22s}: {v[:55]!r}" + (f"   ← {q[:45]!r}" if q and q != 'computed from countries' else ""))