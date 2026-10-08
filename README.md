# Tamis — systematic reviews, sifted

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
packages/core   tamis_core (MIT): parsers, dedup, screening logic, extraction forms,
                LLM calls with usage, PRISMA 2020 SVG renderer
review_app.py   the original single-user Streamlit edition (same engine)
docs/           decision log (every choice and why) and deployment guides
```

## Run the product locally

```bash
# API
pip install -e packages/core -e "apps/api[dev]"
cd apps/api && uvicorn tamis_api.main:app --reload       # http://localhost:8000/docs
# Web
cd apps/web && pnpm install && pnpm dev                   # http://localhost:3000
```

Defaults need no configuration: SQLite database, local PDF folder, e-mails
printed to the console (magic links and invitations are also shown in the
UI in development), jobs run inline. See `.env.example` for production
settings (PostgreSQL, S3-compatible bucket, Resend, included AI credits).

Full stack with Docker: `cp .env.example .env && docker compose up --build`.
Render: `render.yaml` blueprint, see `docs/deploy-render.md`.

## Tests

```bash
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
