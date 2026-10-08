# Systematic review workbench

An open-source, self-hosted tool for running a systematic review from end to
end, in the spirit of Rayyan: import search results, remove duplicates, screen
titles/abstracts and full texts (alone or in a blind team), let an AI fill a
data-extraction form **you** define, verify it against the PDF, and get PRISMA
2020 counts and exports. Interface in English or French.

```
search exports ──▶ import ──▶ duplicates ──▶ title/abstract ──▶ full text ──▶ extraction ──▶ PRISMA & export
 RIS · BibTeX       biblio.py   dedup.py       screening.py       + PDFs        extraction_schema.py
 PubMed · WoS                                  (per reviewer,     (Unpaywall    (your fields, AI draft,
 CSV · Excel                                   blind, AI hints)   or upload)    human verification)
```

Everything lives in one SQLite file (`review.db`) plus a folder of PDFs, so a
laptop, a lab server or a Render/Fly/VPS container all work the same way.

## Run it

```bash
pip install -r requirements.txt
streamlit run review_app.py
```

Optional environment variables: `DATA_DIR` (where `review.db` and PDFs are
stored; defaults to the app folder), `APP_LANG` (`en` or `fr`),
`ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` (only for the AI
features), `UNPAYWALL_EMAIL` (to fetch open-access PDFs by DOI), `REVIEWER`
(default reviewer name).

### Docker

```bash
cp .env.example .env            # add your keys if you want the AI features
docker compose up --build       # http://localhost:8501, data in the review_data volume
```

### Render

`render.yaml` is a Render blueprint: one Docker web service with a 5 GB
persistent disk mounted on `/data` (persistent disks need a paid instance).
Create a new Blueprint from the repository, then add the API keys in the
Render dashboard. The container binds to Render's `PORT` automatically.

## The seven stages

1. **Setup** – project name, research question, inclusion/exclusion criteria,
   exclusion reasons offered during screening, keywords highlighted in green
   and red in abstracts, number of reviewers needed per record (1 = single,
   2 = double screening with conflict resolution). Below it, the **extraction
   form**: a table of fields (name, label, kind, options, instruction for the
   AI, required). Kinds: `text`, `sentences`, `number`, `year`, `yesno`,
   `enum`, `multi`, `list`. Import/export the form as JSON or CSV, or load the
   52-field energy-modelling template that ships with the repository.
2. **Import** – drop RIS, BibTeX, PubMed `.nbib`, Web of Science `.txt`,
   CSV/TSV (Scopus, WoS, Zotero, Google Scholar…) or Excel exports. Formats
   are detected from content, not only from the extension. Each file is kept
   as a batch you can delete.
3. **Duplicates** – same DOI and identical normalised titles are merged
   automatically. Similar titles are merged above the first threshold when the
   year or the first author agrees, and listed as *possible duplicates* above
   the second threshold for you to confirm. The most complete record is kept
   and its gaps are filled from the others; sources are merged for PRISMA.
   Anything can be restored.
4. **Title & abstract screening** – one record at a time with highlighted
   keywords, Include / Maybe / Exclude (+ reason, labels, note), views for
   to-screen / included / excluded / conflicts, free-text search, blind mode,
   conflict resolution recorded as "consensus". Optional **AI pre-screening**
   proposes a decision with a rationale and confidence; you accept or ignore it.
5. **Full-text screening** – upload the PDF or fetch an open-access copy by
   DOI through Unpaywall, read it in the app, decide with a reason, or flag
   the report as not retrievable (counted in PRISMA).
6. **Extraction** – for every study included at full text, the AI fills your
   form from the PDF with a verbatim quote per field. You verify side by side
   with the PDF; a checker flags empty required fields, values outside the
   allowed options, bad years and fields without a supporting quote. Verified
   extractions export to Excel/CSV (one sheet of values, one of quotes).
7. **PRISMA & export** – PRISMA 2020 counts (identified per source, duplicates,
   screened, excluded, sought, not retrieved, assessed, excluded with reasons,
   included), a flow diagram, and exports: included studies (RIS/CSV), all
   records with status, decision log, extractions, PRISMA counts, DOT diagram.

## AI providers

The AI is optional and never decides for you. Three providers are supported
through `extractor.py`: Anthropic (Claude), Google (Gemini) and DeepSeek. Set
the key in the sidebar or as an environment variable, and pick any model ID.
A cheap model is fine for screening; use a stronger one for extraction.

## Repository layout

| File | Role |
| --- | --- |
| `review_app.py` | The Streamlit workbench (all seven stages) |
| `biblio.py` | Parsers (RIS, BibTeX, PubMed, Web of Science, CSV/Excel) and RIS/CSV writers |
| `dedup.py` | Duplicate detection (DOI, exact title, fuzzy title) and merging |
| `screening.py` | Reviewer consensus, keyword highlighting, AI screening prompt |
| `extraction_schema.py` | Author-defined extraction fields: prompt, cleaning, checks, templates |
| `review_db.py` | SQLite storage (projects, records, decisions, suggestions, extractions) |
| `i18n.py` | English and French interface strings |
| `extractor.py` | PDF text extraction, LLM calls, Unpaywall lookup (shared with the legacy app) |
| `extraction_app.py`, `anomalies.py` | The original energy-modelling extraction app this project grew from |
| `tests/` | pytest suite (parsers, dedup, screening, schema, storage, app smoke test) |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

The suite needs no API key and no browser: the app is exercised with
Streamlit's `AppTest`.

## Limitations and next steps

- Single SQLite database: fine for a small team on one server, not for
  hundreds of concurrent users. Swapping to Postgres is a localised change in
  `review_db.py`.
- No accounts: reviewers identify themselves by name. Put the app behind an
  authentication proxy if it is exposed on the internet.
- Streamlit has no keyboard shortcuts, so screening is mouse-driven.
- Scanned PDFs need OCR before extraction.

## Contributing / adding a language

Copy the `"en"` block of `i18n.py`, translate it, and add the code to
`LANGUAGES`. Missing keys fall back to English.

## License

MIT (see `LICENSE`).
