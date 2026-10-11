<<<<<<< HEAD
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
=======
# Krinea — systematic reviews, sifted

Open-source workbench for systematic reviews, in the spirit of Rayyan or
Covidence but yours to host: import search exports, remove duplicates, screen
titles/abstracts and full texts with your team (blind double screening,
conflicts, keyboard shortcuts, highlighted keywords), let an AI fill the
data-extraction form **you** define with a verbatim quote per field, verify
beside the PDF, and report with the official PRISMA 2020 flow diagram.
English and French interface. AGPL-3.0 application, MIT core engine.

```
apps/web        Next.js 16 product: marketing site + application (en/fr)
apps/api        FastAPI + SQLAlchemy: accounts, reviews, imports, dedup, screening,
                AI jobs, extraction, PRISMA, exports; PostgreSQL or SQLite
packages/core   krinea_core (MIT): parsers, dedup, screening logic, extraction forms,
                LLM calls with usage, PRISMA 2020 SVG renderer
review_app.py   the original single-user Streamlit edition (same engine)
docs/           decision log (every choice and why) and deployment guides
```

## Run the product locally

```bash
# API
pip install -e packages/core -e "apps/api[dev]"
cd apps/api && uvicorn krinea_api.main:app --reload       # http://localhost:8000/docs
# Web
cd apps/web && pnpm install && pnpm dev                   # http://localhost:3000
```

Defaults need no configuration: SQLite database, local PDF folder, e-mails
printed to the console (magic links and invitations are also shown in the
UI in development), jobs run inline. See `.env.example` for production
settings (PostgreSQL, S3-compatible bucket, Resend, included AI credits).

Full stack with Docker: `cp .env.example .env && docker compose up --build`.
Render: `render.yaml` blueprint, see `docs/deploy-render.md`.

## Sign in with Google

Optional. In Google Cloud Console create a project, configure the OAuth
consent screen (external, scopes `openid`, `email`, `profile`), then
**Credentials → Create credentials → OAuth client ID → Web application** with
the authorised redirect URI `https://<your-domain>/api/auth/google/callback`
(and `http://localhost:3000/api/auth/google/callback` for development). Put
the client id and secret in `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` of the
API. The "Continue with Google" button appears on the sign-in and sign-up
pages as soon as both variables are set; accounts are matched by verified
e-mail, so a Google sign-in attaches to an existing password account with
the same address.

## One origin: the web app proxies the API

Browsers never call the API directly. The web app forwards `/api/*` to the
API (`API_URL`, an internal address in production) and passes cookies
through, so the session cookie is first-party, there is no CORS, and only
one domain is needed (decision D-23). The API builds links (magic links,
invitations, Google redirects) from `BASE_URL` when set, otherwise from the
origin the proxy reports, which it trusts because the web app's `PROXY_KEY`
equals the API's `SECRET_KEY`. Set `NEXT_PUBLIC_API_URL` only when the API
is hosted separately and called directly.
>>>>>>> d4ff4f6bba015c2b901ce172bd9a1553a3c5810d

## Tests

```bash
<<<<<<< HEAD
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
=======
cd apps/api && pytest -q        # accounts and a two-reviewer end-to-end flow (stubbed LLM)
python -m pytest -q             # engine and Streamlit edition (repository root)
cd apps/web && pnpm build       # type-checks and builds the web app
```

## Streamlit edition

```bash
pip install -r requirements.txt && streamlit run review_app.py
```
Single researcher, one container, SQLite; same import/dedup/screening/
extraction/PRISMA pipeline. Dockerfile at the root.

## Status and roadmap

Working today: accounts (password, magic link), reviews with roles and
e-mail invitations, imports (RIS, BibTeX, PubMed, Web of Science, CSV,
Excel), duplicate detection with reviewable candidates, title/abstract and
full-text screening with blind mode and consensus, PDF upload and
open-access lookup, AI screening suggestions and extraction drafts through a
job queue (bring your own key, or included credits), author-defined
extraction forms with verification, PRISMA 2020 diagram and exports.

Next: billing (Stripe) and plan limits, ORCID/Google sign-in, Rayyan and
Covidence importers, abstract-based duplicate signals, extraction dashboards,
dark-mode toggle, Alembic migrations. Decisions and rationale:
`docs/decisions.md`.

## Licence

Application: AGPL-3.0-only (`LICENSE`). `packages/core`: MIT
(`packages/core/LICENSE`). PRISMA 2020 templates are reproduced under CC BY
4.0 (prisma-statement.org).
>>>>>>> d4ff4f6bba015c2b901ce172bd9a1553a3c5810d
