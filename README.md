# Krinea

Systematic reviews, judged on the evidence.

Open-source workbench for systematic reviews, in the spirit of Rayyan or
Covidence but yours to host: import search exports, remove duplicates, screen
titles/abstracts and full texts with your team (blind double screening,
conflicts, keyboard shortcuts, highlighted keywords), let an AI fill the
data-extraction form **you** define with a verbatim quote per field, verify
beside the PDF, and report with the official PRISMA 2020 flow diagram.
English and French interface. AGPL-3.0 application, MIT core engine.

Source code: <https://github.com/aymardino/krinea>. Hosted beta:
<https://krinea.org>.

```
apps/web        Next.js 16 product: marketing site + application (en/fr)
apps/api        FastAPI + SQLAlchemy: accounts, reviews, imports, dedup, screening,
                AI jobs, extraction, PRISMA, exports; PostgreSQL or SQLite
packages/core   krinea_core (MIT): parsers, dedup, screening logic, extraction forms,
                LLM calls with usage, PDF text, Unpaywall lookup, PRISMA 2020 SVG renderer
review_app.py   the original single-user Streamlit edition (same engine)
docs/           decision log (every choice and why) and deployment guides
```

## Run the product locally

```bash
git clone https://github.com/aymardino/krinea && cd krinea
# API
pip install -e packages/core -e "apps/api[dev]"
cd apps/api && uvicorn krinea_api.main:app --reload       # http://localhost:8000/docs
# Web (second terminal)
cd apps/web && pnpm install && pnpm dev                   # http://localhost:3000
```

Defaults need no configuration: SQLite database, local PDF folder, e-mails
printed to the console (in development, invitation links are also shown in
the UI, and so is the sign-in link when the app runs on `localhost`), jobs
run inline. Every API setting is
listed in `apps/api/README.md`; `.env.example` shows a production setup
(PostgreSQL, S3-compatible bucket, SMTP or Resend e-mail, included AI
credits).

On a public server set `KRINEA_ENV=production`. The API then refuses to
start without a real `SECRET_KEY` (at least 16 characters, not a
placeholder such as `change-me`), and refuses to send e-mail until
`EMAIL_PROVIDER` is `smtp` or `resend` with complete settings: invitations
answer `502` with the reason and the sign-in page hides the e-mail-link
option.

Full stack with Docker: `cp .env.example .env`, set `SECRET_KEY` in `.env`
to a long random value (for example the output of
`python -c "import secrets; print(secrets.token_urlsafe(48))"`), then
`docker compose up --build`. Compose stops with a message when `SECRET_KEY`
is missing. Render: `render.yaml` blueprint, see `docs/deploy-render.md`.

## Sign in with Google

Optional. In Google Cloud Console create a project, configure the OAuth
consent screen (external, scopes `openid`, `email`, `profile`), then
**Credentials → Create credentials → OAuth client ID → Web application** with
the authorised redirect URI `https://<your-domain>/api/auth/google/callback`
(and `http://localhost:3000/api/auth/google/callback` for development). Put
the client id and secret in `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` of the
API. The "Continue with Google" button appears on the sign-in and sign-up
pages as soon as both variables are set. Accounts are matched by verified
e-mail, so a Google sign-in attaches to an existing account with the same
address. When that address had never been verified (no earlier sign-in
link or Google sign-in), the account's password is cleared and its other
sessions are closed, so nobody can pre-register someone else's address and
keep access to it; the same applies to the first e-mail sign-in link.

## One origin: the web app proxies the API

Browsers never call the API directly. The web app forwards `/api/*` to the
API (`API_URL`, an internal address in production) and passes cookies
through, so the session cookie is first-party, there is no CORS, and only
one domain is needed (decision D-23).

The API builds links (sign-in links, invitations, Google redirects) from
`BASE_URL` when it is set, which is required in production. Otherwise it
uses the origin the proxy reports, which it trusts because the web app's
`PROXY_KEY` equals the API's `SECRET_KEY`. The proxy never derives that
origin from client headers (`Host`, `X-Forwarded-Host`, `X-Forwarded-Proto`):
in production it sends `PUBLIC_ORIGIN` (read at run time) or
`NEXT_PUBLIC_SITE_URL` (baked in at build time, default
`https://krinea.org`); only in development does it use the `Host` header.
Set `NEXT_PUBLIC_API_URL` only when the API is hosted separately and called
directly.

## Tests

```bash
pip install -r requirements-dev.txt && python -m pytest -q   # repository root: engine, root shims, Streamlit edition
cd apps/api && python -m pytest -q                           # API: accounts, PDFs, a two-reviewer end-to-end flow (stubbed LLM)
cd apps/web && pnpm build                                    # type-checks and builds the web app
```

The API suite needs `pip install -e packages/core -e "apps/api[dev]"`.
Continuous integration (`.github/workflows/ci.yml`) runs the root and API
test suites and the web build on every push and pull request.

## Streamlit edition

```bash
pip install -r requirements.txt && streamlit run review_app.py
```

Run it from the repository root: `requirements.txt` installs the engine
from `./packages/core` (with its `excel` and `llm` extras). Single
researcher, one container, SQLite; same import/dedup/screening/
extraction/PRISMA pipeline. The root `Dockerfile` builds it as one image
(`docker build -t krinea-streamlit . && docker run -p 8501:8501 -v
krinea_streamlit:/data krinea-streamlit`).

## Status and roadmap

Working today: accounts (password, magic link, Google), reviews with roles and
e-mail invitations, imports (RIS, BibTeX, PubMed, Web of Science, CSV,
Excel), duplicate detection with reviewable candidates, title/abstract and
full-text screening with blind mode and consensus, PDF upload and
open-access lookup, AI screening suggestions and extraction drafts through a
job queue (bring your own key, or included credits), author-defined
extraction forms with verification, PRISMA 2020 diagram and exports.

Next: billing (Stripe) and plan limits, ORCID sign-in, Rayyan and
Covidence importers, abstract-based duplicate signals, extraction dashboards,
dark-mode toggle, Alembic migrations. Decisions and rationale:
`docs/decisions.md`.

## Contributing

Contributions are welcome: see `CONTRIBUTING.md` (setup, tests, licences per
directory, sign-off with `git commit -s`). Everyone taking part follows the
`CODE_OF_CONDUCT.md`.

## Security

Never report a vulnerability in a public issue. Write privately to
contact@krinea.org or use GitHub private vulnerability reporting; details in
`SECURITY.md`.

## Citation

Cite the release (version shown in the site footer, currently 0.1.0) and the
repository URL. `CITATION.cff` holds the metadata; GitHub shows it as "Cite
this repository".

## Supporting the project

Krinea is free and self-hosting stays free. The hosted edition costs money every month (servers, domain name, mailbox); if it saves you time, you can [buy the maintainer a coffee](https://www.buymeacoffee.com/aymardinho). Donations are voluntary, unlock nothing and are not tax deductible.

## Licence

Application: AGPL-3.0-only (`LICENSE`). `packages/core`: MIT
(`packages/core/LICENSE`). PRISMA 2020 templates are reproduced under CC BY
4.0 (prisma-statement.org).
