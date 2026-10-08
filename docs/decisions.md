# Decision log

Every product or technical decision taken on this project, in order, with the
reason and what it would cost to reverse. Entries marked **proposed** are
recommendations waiting for the owner's answer; they become decisions once
confirmed (or are replaced by what the owner chooses).

Format: number · date · status · decision · why · consequences / how to undo.

---

## D-01 · 2026-10-08 · decided · Do not modify `extraction_tool`, work in a duplicate

**Decision.** The original repository `aymardino/extraction_tool` is left
untouched. All work happens in a copy, now `aymardino/systematic_review`.

**Why.** Owner's instruction. The original app is in daily use for the
EnerMod Africa corpus and must keep working as is.

**Consequences.** Fixes made in the new repository are not back-ported
automatically. Undo: none needed, the original is intact.

## D-02 · 2026-10-08 · decided · Remove the cached PDFs from the whole git history

**Decision.** `_pdf_cache/` (≈3.3 GB of copyrighted article PDFs) was
removed from every commit of the duplicate, not only from the working tree.

**Why.** Owner's instruction; GitHub refuses pushes above 2 GB; the PDFs are
third-party copyrighted material that should not ship in an open-source
repository. Result: 2.84 GB → 58 MB.

**Consequences.** The duplicate's commit hashes differ from the original's.
`extractions.db` (the 436 verified extractions, 51 MB) was kept. Undo:
impossible in this repository, but the original still has everything.

## D-03 · 2026-10-08 · decided · New GitHub repository, private at creation

**Decision.** Code lives in `aymardino/systematic_review`, created private by
the owner (the session's GitHub integration cannot create repositories).

**Why.** A separate home for a product that will diverge from the original
tool. Private first because publishing is a one-way door; flipping to public
is one click.

**Consequences.** Make it public when the licence (D-13) and name (P-01) are
settled.

## D-04 · 2026-10-08 · decided · English for code, docs and default UI; French available in the UI

**Decision.** Source code, comments, commit messages and documentation are in
English. The interface ships in English and French with a language switch;
strings live in `i18n.py` (one dictionary per language).

**Why.** Owner's instruction; an open-source project reaches more
contributors in English; researchers in Africa work in both languages.

**Consequences.** Every new UI string needs an entry in both languages (a
test fails otherwise). Adding a language = one more dictionary.

## D-05 · 2026-10-08 · decided · Streamlit for the first version, a full web stack for the product

**Decision.** Version 1 (`review_app.py`) is a Streamlit application reusing
the existing extraction code. The product version will be a separate web
application (see P-04) with the same Python core modules.

**Why.** Streamlit gave a working seven-stage pipeline in one day, and it
validated the domain logic (parsers, dedup, screening, extraction schema)
which carries over unchanged. Streamlit cannot provide accounts, keyboard
shortcuts, a marketing site or a polished product feel.

**Consequences.** Two front ends for a while. The Streamlit app stays as the
free self-hosted "single researcher" edition.

## D-06 · 2026-10-08 · decided · SQLite for version 1, PostgreSQL for the product

**Decision.** `review.db` (SQLite) for the Streamlit edition. The web product
uses PostgreSQL from day one.

**Why.** SQLite is zero-setup and perfect for one container with a persistent
disk. PostgreSQL is needed as soon as several users write concurrently,
sessions run on several instances, or Render's managed database is used
(Render has no persistent disk on free instances, and a disk pins the
service to one instance).

**Consequences.** The product's data layer is written with SQLAlchemy so the
schema is shared; the Streamlit edition can later point at PostgreSQL too.

## D-07 · 2026-10-08 · decided · The author defines the extraction form

**Decision.** Extraction fields are per project (name, label, kind, options,
instruction for the AI, required), edited in the app, importable as JSON/CSV.
The former fixed 52-field energy schema is an importable template.

**Why.** Owner's instruction. A review tool must serve any discipline.

**Consequences.** The AI prompt, the verification form and the exports are
generated from the schema. Domain-specific consistency rules (power pools,
ISO codes) do not apply to arbitrary schemas; only generic checks do.

## D-08 · 2026-10-08 · decided · Duplicate detection strategy

**Decision.** Three signals: identical DOI; identical normalised title;
fuzzy title similarity (rapidfuzz ratio) restricted to records whose years
are within one year of each other. A fuzzy match is merged automatically
above 95 % when the year or the first author agrees and the DOIs do not
conflict; between 85 % and 95 % (or without corroboration) it is queued for
a human. The most complete record is kept and its gaps filled from the
others; sources are merged for PRISMA counts.

**Why.** DOI and title are the signals with the best precision; year and
first author remove most false positives (series of papers with near-identical
titles). Thresholds are sliders in the UI.

**Consequences.** Planned enrichment (P-07): abstract similarity as a
corroborating signal and PMID/other identifiers.

## D-09 · 2026-10-08 · decided · Screening model: one decision per reviewer and stage, consensus by rule

**Decision.** Decisions are stored per (record, stage, reviewer). A record's
status is computed: pending until the required number of reviewers decided;
include/exclude when they agree; maybe when one says maybe; conflict
otherwise. A decision recorded under the reviewer name `consensus` settles a
conflict. Blind mode hides other reviewers' decisions.

**Why.** Mirrors Rayyan's single/double screening and conflict resolution
with the simplest possible storage.

**Consequences.** The decision log is a complete audit trail (exported as
CSV). Reviewers are identified by name in version 1; by account in the
product.

## D-10 · 2026-10-08 · decided · AI is advisory, never decisive

**Decision.** AI suggestions (screening) and AI drafts (extraction) are
stored separately from human decisions and always require a human action to
become a decision. Every extracted value carries a verbatim quote.

**Why.** Methodological acceptability (PRISMA, Cochrane) and trust: the
reviewer must remain accountable for every inclusion.

**Consequences.** The product can offer "accept all suggestions above X %
confidence" as an explicit, logged bulk action, never as a default.

## D-11 · 2026-10-08 · decided · Visual identity of version 1

**Decision.** Light theme, teal primary (#0E7490), header band, stage
navigation as pills, bordered cards, green/red keyword highlighting.

**Why.** Readable for hours of screening; neutral enough to rebrand once the
name is chosen.

**Consequences.** The product gets a proper design system (P-05); the
Streamlit theme follows it.

## D-12 · 2026-10-08 · decided · Deployment of version 1: Docker + Render blueprint

**Decision.** `Dockerfile`, `docker-compose.yml` and `render.yaml` (one
Docker web service, persistent disk on `/data`, port taken from `PORT`).

**Why.** Owner wants Render; Docker keeps self-hosting identical.

**Consequences.** Persistent disks need a paid Render instance. See
`docs/deploy-render.md`.

## D-13 · 2026-10-08 · decided · Licence: AGPL-3.0 for the application, MIT for the core modules

**Decision.** The application (web app, API, Streamlit edition) is licensed
under AGPL-3.0. The reusable core modules (bibliographic parsers,
deduplication, screening logic, extraction schema) are licensed under MIT so
other tools can embed them.

**Why.** Owner's choice. AGPL keeps the code open and self-hostable while
obliging anyone who offers it as a hosted service to publish their changes,
which protects the paid hosted offer (D-15). MIT on the core maximises reuse
and goodwill in the research-software community.

**Consequences.** `LICENSE` at the root is AGPL-3.0; `packages/core/LICENSE`
is MIT; every source file states its licence in the header. Contributors
accept both. The MIT licence file added earlier at the root is replaced.

## D-14 · 2026-10-08 · decided · Product name: Tamis

**Decision.** The product is called **Tamis** (French for sieve). Repository,
package names, domain and brand follow (`tamis`, `tamis.app` to be
registered by the owner; `tamis.com` is probably taken).

**Why.** Owner's choice among the shortlist. One word, pronounceable in
French and English, describes exactly what the tool does with a search
(it sifts), and the mesh motif gives a natural logo.

**Consequences.** Rename the GitHub repository to `aymardino/tamis` (GitHub
keeps a redirect from the old name). Check trademark collisions before
launch. Register `tamis.app` and, if free, `tamis.io`.

## D-15 · 2026-10-08 · decided · Business model: open source + paid hosted service

**Decision.** The code is open source (D-13) and self-hostable for free. The
owner runs a hosted service at the product domain with three tiers:
**Free** (hosted, limits on active reviews and collaborators, bring your own
AI key), **Pro** (unlimited reviews, team features, included AI credits,
priority support), **Institution** (SSO, admin console, invoicing, data
residency). Free access for reviewers in low-income countries.

**Why.** Owner's choice. It is the model that universities trust (they can
audit and self-host) and that still funds hosting and development.
Reference points: Rayyan (Free / Essential / Advanced individual tiers,
Professional at about USD 8 per month billed yearly) and Covidence (USD 339
per review per year).

**Consequences.** The marketing site has a pricing page; billing (Stripe) and
plan limits are part of phase 4; usage metering starts in phase 1 so limits
can be enforced later.

## D-16 · 2026-10-08 · decided · AI access: bring your own key, plus included credits on paid tiers

**Decision.** Any user may store their own provider key (Anthropic, Google,
DeepSeek), encrypted at rest per user and never logged. Paid tiers include a
monthly AI budget billed at provider cost plus margin, shown as a meter in
the app. The self-hosted edition supports keys only.

**Why.** Owner's choice. Keys keep the free edition useful without the
project paying for inference; credits remove the setup barrier for
non-technical teams.

**Consequences.** The API needs a key vault (encryption key in the
environment), per-call cost accounting, and a hard stop when the budget is
exhausted. Model choice stays per project.

## D-17 · 2026-10-08 · decided · Product architecture and stack

**Decision.** Monorepo: `apps/api` (Python 3.11+, FastAPI, SQLAlchemy 2,
Alembic, PostgreSQL in production, SQLite for local development and tests),
`apps/web` (Next.js App Router, TypeScript, Tailwind, shadcn/ui, next-intl
for en/fr, TanStack Query), `packages/core` (the Python modules already
written). Background jobs run from a database-backed queue processed by a
worker process (no Redis at first). PDFs go to local disk in development
and to an S3-compatible bucket in production. Authentication: email and
password (argon2) plus magic links; Google and ORCID sign-in later.

**Why.** Reuses everything built so far; FastAPI and Next.js are the most
common pairing for this kind of product and are well supported on Render;
a database queue avoids a paid Key Value instance until load justifies it.

**Consequences.** Two languages in the repository (Python, TypeScript); CI
runs both test suites. The Streamlit edition keeps working from
`packages/core`.

## D-18 · 2026-10-08 · decided · Tamis visual identity

**Decision.** Typeface Inter for the interface and a serif (Source Serif 4)
for marketing headings; palette built on a deep teal primary (sieve/mesh
motif), warm amber accent for highlights and progress, slate neutrals;
semantic colours for decisions: green include, amber maybe, red exclude.
Light and dark themes from the same tokens. The screening workflow follows
the conventions every review tool shares (a queue of records, a reading
pane, decisions, filters, a progress overview) but the layout, components,
icons, copy and visual language are Tamis's own: no element of Rayyan's
interface is reproduced (see D-19). Keyboard shortcuts I / M / E and arrows.

**Why.** Distinct from Rayyan's indigo and Covidence's palette, readable for
long sessions, and the mesh motif makes the name visible. An original design
is also the legal posture (D-19).

**Consequences.** Tokens live in `apps/web` (CSS variables) and are mirrored
in the Streamlit theme. Rayyan screenshots are used only to list features,
never as a visual reference during design work.

## D-19 · 2026-10-08 · decided · Legal posture towards competitors

**Decision.** Tamis competes on features and openness, never by copying.
Rules: no competitor name in the product, domain, logo or metadata; no
competitor UI code, graphics, icons, colours, screenshots or copy in the
codebase or the marketing site; original layout and visual language;
comparisons on the website only as factual, verifiable statements (price,
licence, self-hosting, features) without denigration; migration helpers
only read the user's own exported files; third-party dependencies tracked
with their licences; privacy policy, terms of service and a GDPR data
processing agreement before the hosted service takes payments; hosting in
an EU region.

**Why.** Workflows and features of review software are not protected by
copyright, and building a competitor is lawful. The residual risks are
copyright on expression (code, graphics, text), trademark confusion, and, in
French law, unfair competition or parasitism when a look and feel is copied
slavishly. The rules above remove those risks. This is a working posture,
not legal advice: a lawyer reviews the terms and the brand before launch.

**Consequences.** Design reviews check originality; a `THIRD_PARTY_NOTICES`
file lists dependencies; the brand name is checked and filed as a trademark
before public launch.

---

## Proposed decisions (waiting for the owner)

P-01 to P-05 were decided on 2026-10-08 (see D-13 to D-18).

## D-22 · 2026-10-08 · decided · Sign in with Google (OpenID Connect)

**Decision.** Google sign-in uses the authorization-code flow handled entirely
by the API (`/auth/google/start`, `/auth/google/callback`): signed state and
nonce in a short-lived cookie, local verification of the ID token against
Google's keys, accounts matched by verified e-mail and stored as external
identities (`oauth_accounts`), so ORCID can follow the same path. The web app
only shows the button when the API reports the provider as configured.

**Why.** Researchers already have Google accounts; keeping the flow in the API
means one session mechanism (the same cookie) for every sign-in method and no
secrets in the browser.

**Consequences.** Needs an OAuth client in Google Cloud Console per
environment and `API_URL` set to the public API address.

### P-06 · PRISMA 2020

Recommendation: reproduce the official PRISMA 2020 template exactly (three
side bands Identification / Screening / Included, the two database/other
sources variants, grey optional boxes), rendered as SVG in the app and
exported as PNG, SVG and DOCX. The templates are CC BY 4.0.

### P-07 · Duplicates on abstract and keywords

Recommendation: keep title/DOI as primary signals and add abstract
similarity (TF-IDF cosine or MinHash) and shared keywords as corroboration
for the 85–95 % band, with the similarity breakdown shown to the reviewer.
Abstract-only matches are never auto-merged (conference vs journal versions
share abstracts but are different reports).

### P-08 · Charts and analytics

Recommendation: overview dashboard (imported per source, duplicates,
decisions donut, conflicts, throughput per reviewer and per day, time per
record), screening keyword counts for include/exclude filters, year and
journal distributions, source overlap, extraction dashboards per field
(counts per option, numeric distributions), all exportable.

## D-20 · 2026-10-08 · decided · Tamis product, first implementation

**Decision.** The product exists as a monorepo: `packages/core` (MIT engine),
`apps/api` (FastAPI, SQLAlchemy, PostgreSQL/SQLite), `apps/web` (Next.js 16,
TypeScript, Tailwind 4, next-intl, Radix UI primitives with Tamis's own
components, because the shadcn CLI needs network access the build
environment does not have). Fonts are embedded (Inter, Source Serif 4 via
fontsource) so builds never call Google. Charts are hand-written SVG/HTML
following the data-visualisation rules (one axis, status colours only for
statuses, labels in text ink, hover tooltips); the decision colours were
validated for colour-vision deficiency in light mode (amber moved from
#b45309 to #d97706 so that "maybe" and "exclude" stay distinguishable).

**Why.** Everything in D-17 and D-18, delivered; the environment constraints
dictated the two substitutions above.

**Consequences.** Dark mode has tokens but no toggle yet; its amber/green
pair sits in the validator's warning band and is acceptable only because
every status is also labelled. Alembic migrations replace `create_all` once
the schema stabilises. Billing (Stripe), SSO/ORCID sign-in, Rayyan/Covidence
importers, abstract-based duplicate signals and per-field extraction
dashboards are the next increments (see P-06 to P-08).

## D-21 · 2026-10-08 · decided · Deployment topology

**Decision.** Four services: `tamis-web` (Next.js standalone image),
`tamis-api` (Docker, uvicorn), `tamis-worker` (same image, `python -m
tamis_api.worker`), managed PostgreSQL. PDFs go to an S3-compatible bucket
in production (`S3_BUCKET`), or to a disk mounted at `/data` for small
self-hosted setups. `docker-compose.yml` runs the same four services on one
machine; `render.yaml` is the Render blueprint (region Frankfurt, EU). The
Streamlit edition keeps its own single-container Dockerfile at the root.

**Why.** D-17; separating the worker keeps AI batches off the request path;
a bucket keeps the API stateless so Render can scale it and no paid disk is
needed.

**Consequences.** DNS: apex to `tamis-web`, `api.` to `tamis-api`; cookies
are same-site across the two hosts. Secrets (`SECRET_KEY`, provider keys,
Resend, bucket credentials) live in the Render dashboard.

## D-23 · 2026-10-08 · decided · One public origin: the web app proxies the API

**Decision.** Browsers only talk to the web app. `apps/web/src/app/api/[...path]/route.ts`
forwards `/api/*` to the API (`API_URL`, an internal address in production) and streams
the response back, cookies included. The API builds public links (magic links,
invitations, Google redirects) from `BASE_URL` when set, otherwise from the origin the
proxy reports in `X-Tamis-Origin`, trusted only when `X-Tamis-Proxy-Key` equals the
API's `SECRET_KEY`. `DATABASE_URL` values of the form `postgres://` or `postgresql://`
are rewritten to the psycopg driver. `render.yaml` no longer hard-codes any domain.

**Why.** The first Render deployment failed three ways: Render's PostgreSQL URL
(`postgres://`) made SQLAlchemy crash at startup (hence the "server failure" mails), the
blueprint pointed the browser at `api.tamis.app` before any domain existed, and two
`onrender.com` hosts are different *sites* (the suffix is on the Public Suffix List), so
a `SameSite=Lax` session cookie set by the API would never have been sent by the web app.
One origin removes all three classes of problem and leaves one domain to buy and
configure.

**Consequences.** `NEXT_PUBLIC_API_URL` is no longer baked into the web image and is
only for calling a separately hosted API directly (CORS then applies, with
`CORS_ORIGINS`). The OAuth state cookie is scoped to `/`. The API's public hostname is
unused by the product; a custom domain goes on `tamis-web` only. Large PDF uploads and
exports stream through the Next.js server. Supersedes the DNS note in D-21.

## D-24 · 2026-10-08 · decided · Settings live where they are used

**Decision.** The screening rail edits the highlight keywords in place (chips with
match counts, add with Enter, remove with ×) and the AI panel shows the review's
provider, the key on file or the included credits, and otherwise a field to paste the
provider key right there. The review settings and the user settings keep the full
forms; the rail saves to the same endpoints.

**Why.** Founder feedback on the hosted beta: keywords and the AI key were "too far"
(two pages away) from the screen where they matter, so reviewers did not use them.

**Consequences.** Admin-only for keywords (same rule as the settings page); any
reviewer can add their own key. The run button stays disabled until a key or credits
exist, which replaces the 402 error path for most users.

## D-25 · 2026-10-08 · decided · Marketing site structure and the pages a hosted service needs

**Decision.** Header: Features · Pricing · About, the repository as an icon and a
footer link (no star counter), a menu on phones. Hero in two columns from 1024 px with
the screening preview beside the text. Trust strip with four verifiable facts, pricing
teaser, closing section "Free to try, free to leave". Footer in four columns. New pages
now: /about, /contact, /privacy, /terms, /legal (Markdown under
`apps/web/content/<locale>`, version 0.1 "under legal review"); later: /docs,
/security, /cite, /dpa, /changelog, /accessibility. Pro is a waitlist and the
Institution plan points to /contact until billing and the legal documents exist. No
e-mail address is published until a domain with working mail exists
(`NEXT_PUBLIC_CONTACT_EMAIL`).

**Why.** Three critiques (information architecture, density at 100 % zoom, content and
trust) converged: the source link outweighed the product, the single-column hero left
half the viewport empty and pushed the product below the fold, and accounts already
exist, so GDPR article 13 and LCEN information are due now, not later.

**Consequences.** The legal texts must be read by a lawyer before any paid plan (P-09);
the publisher identity in /legal is withheld under LCEN 6-III as a non-professional
publisher until a legal entity exists. The repository root still carries files of the
original extraction project; moving them to `legacy/` is pending (see the cleanup
proposal of 2026-10-08).

### P-09 · Legal vehicle operating the hosted service

Open-source publication needs no legal entity. Taking payments does. Options
being weighed: a company (SAS) run by a partner who is entitled to manage a
business in France, with the founding researcher as shareholder and
scientific contributor under the public-research "chercheur-entrepreneur"
rules (Code de la recherche L531-1 and following; up to 49 % of the capital,
authorisation by the employing institution); or a non-profit association
hosting the service at cost. Prerequisite in all cases: written
clarification with the employer of who owns the original extraction code
and of the open-source release. Until this is settled, Tamis stays open
source without a paid offer.
