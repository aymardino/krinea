# Decision log

Every product or technical decision taken on this project, in order, with the
reason and what it would cost to reverse. Entries marked **proposed** are
recommendations waiting for the owner's answer; they become decisions once
confirmed (or are replaced by what the owner chooses).

Format: number · date · status · decision · why · consequences / how to undo.

---

## D-01 · 2026-10-08 · decided · Leave the original prototype untouched, work in a copy

**Decision.** The project started as a PDF-extraction prototype for a
research review. The prototype's repository is left untouched; all work
happens in a copy, first named `aymardino/systematic_review`, now
`aymardino/krinea`.

**Why.** Owner's instruction. The prototype was in daily use and had to keep
working as is.

**Consequences.** Fixes made in this repository are not back-ported to the
prototype. Undo: none needed, the original is intact.

## D-02 · 2026-10-08 · decided · Remove the cached PDFs from the whole git history

**Decision.** `_pdf_cache/` (≈3.3 GB of copyrighted article PDFs) was
removed from every commit of the copy, not only from the working tree.

**Why.** Owner's instruction; GitHub refuses pushes above 2 GB; the PDFs are
third-party copyrighted material that should not ship in an open-source
repository. Result: 2.84 GB → 58 MB.

**Consequences.** The copy's commit hashes differ from the prototype's. The
prototype's other data files stayed in the working tree until they were
removed on 2026-10-09 (see D-25). Undo: impossible in this repository, but
the prototype's own repository is unaffected.

## D-03 · 2026-10-08 · decided · New GitHub repository, private at creation

**Decision.** Code lives in `aymardino/systematic_review` (renamed
`aymardino/krinea` since, see D-26), created private by the owner (the
session's GitHub integration cannot create repositories).

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
The former fixed 51-field energy schema is an importable template.

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

**Consequences.** `LICENSE` at the root is AGPL-3.0 (`apps/api` declares
AGPL-3.0-only in its package metadata); `packages/core/LICENSE` is MIT and
`packages/core` declares MIT. A licence header (SPDX identifier) in every
source file is planned, not done yet. Contributors accept both licences and
sign off their commits (DCO, see `CONTRIBUTING.md`). The MIT licence file
added earlier at the root is replaced.

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

**Consequences.** Two languages in the repository (Python, TypeScript). CI
(`.github/workflows/ci.yml`, since D-28) runs the root and API test suites and
the web build on every push and pull request. The Streamlit edition keeps
working from `packages/core`.

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
file listing the dependencies and their licences is planned (not written
yet); the brand name is checked and filed as a trademark before public
launch.

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
environment. Since D-23 no public API address is needed: the callback is
`<public origin>/api/auth/google/callback`.

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
(`NEXT_PUBLIC_CONTACT_EMAIL`); since D-28 that address is contact@krinea.org.

**Why.** Three critiques (information architecture, density at 100 % zoom, content and
trust) converged: the source link outweighed the product, the single-column hero left
half the viewport empty and pushed the product below the fold, and accounts already
exist, so GDPR article 13 and LCEN information are due now, not later.

**Consequences.** The legal texts must be read by a lawyer before any paid plan (P-09);
the publisher identity in /legal is withheld under LCEN 6-III as a non-professional
publisher until a legal entity exists. The files of the original extraction prototype
that still sat at the repository root were removed on 2026-10-09; the core package
took over the three pieces the Streamlit edition used (PDF text, Unpaywall lookup, the
energy template).

## D-26 · 2026-10-09 · decided · Renamed Tamis → Krinea

**Decision.** The product, packages (`krinea_core`, `krinea_api`), cookie, proxy headers,
Render service names, site copy and legal texts are renamed to **Krinea** (Greek *krinō*:
to separate, to judge; root of *criterion*). New mark: a circle divided by a diagonal,
two filled dots on the kept side, one hollow dot on the other. Taglines: "Systematic
reviews, judged on the evidence." / "La revue systématique, jugée sur pièces."
Domain: krinea.org (and .app when available).

**Why.** "Tamis" is a common word in French and English (a kitchen sieve) and, worse,
TAMIS is an established surgical acronym (transanal minimally invasive surgery) with
many systematic reviews on PubMed: the exact audience of this tool would have found
colorectal surgery when searching the name. Two naming rounds vetted candidates
against the web, GitHub and the founder's INPI search; Krinea had no indexed use and no
trademark hit.

**Consequences.** Earlier entries keep the historical name. GitHub repository renamed
to `aymardino/krinea` (old URLs redirect); Render services to be renamed in the
dashboard before the next blueprint sync; the first citation of the software must use
the new name.

## D-27 · 2026-10-09 · decided · One sans-serif family; wide-screen layouts

**Decision.** Headings use the same family as the body (Inter), bold, with tighter
letter-spacing; the serif display face of D-18 is dropped. The marketing container
grows to 1 400 px from 1 536 px wide, the application to 1 600 px; the screening
workbench's side columns widen on those screens.

**Why.** Founder feedback on the live site: the serif headlines read as a template
rather than as the research tools people already use, and on a 1 900 px screen the
1 150 px column left too much empty space, in the application as well as on the
marketing pages.

**Consequences.** Brand images regenerated in the sans-serif; `font-display` remains as
a class so no markup changed. Readability keeps a line length under about 80 characters
in text columns (prose pages stay at 768 px).

## D-28 · 2026-10-12 · decided · Audit after the 2026-10-11 merge

**Decision.** A review of the repository after the merge of an old local branch on
2026-10-11 led to these fixes, all in place:

- **Root shims.** `biblio.py`, `dedup.py`, `screening.py` and `extraction_schema.py` at the
  root are again shims to `krinea_core` (the merge had replaced them with stale copies).
  `tests/test_shims.py` fails as soon as a root module stops being the engine module.
  `requirements.txt` installs `./packages/core`, and the root `Dockerfile` copies it.
- **Account pre-hijacking.** When a sign-in link or a Google sign-in verifies an address
  that had never been verified, the API clears the account's password and deletes its
  other sessions, so whoever registered the address first loses access.
- **Public origin from configuration only.** The web proxy no longer derives the origin
  it reports to the API from client headers (`X-Forwarded-Host`, `X-Forwarded-Proto`). In
  production it sends `PUBLIC_ORIGIN` (run time) or `NEXT_PUBLIC_SITE_URL` (build time,
  default `https://krinea.org`); only in development does it use the `Host` header. The
  API still prefers `BASE_URL`, which `render.yaml` declares on `tamis-api` (`sync:
  false`) and which is required in production.
- **`dev_link` fail-safe.** The sign-in link is returned in the API response only when
  debug mode is on and the link's host is `localhost` or `127.0.0.1`.
- **Secret guard.** With `KRINEA_ENV=production` the API refuses to start when
  `SECRET_KEY` is empty, shorter than 16 characters or a known placeholder (`change-me`,
  `change-me-in-production`, `dev-secret-change-me`); `docker-compose.yml` requires
  `SECRET_KEY` (`${SECRET_KEY:?…}`).
- **PDF deletion and purge.** Deleting a review, records or an import deletes their
  stored PDFs (local disk or S3). The worker deletes sign-in-link tokens older than a day
  and expired sessions, at most once an hour.
- **E-mail.** The hosted service sends through an SMTP mailbox at OVHcloud (France, EU)
  for krinea.org (`ssl0.ovh.net`, port 465); Resend remains an option. In production
  without a configured provider the API refuses to send (`502` with the reason) and the
  sign-in page hides the e-mail-link option. The public contact address is
  contact@krinea.org.
- **Compose and environment.** `docker-compose.yml` passes the SMTP and S3 settings and
  `PUBLIC_ORIGIN`, and binds the API port to the local machine only.
- **CI.** `.github/workflows/ci.yml` runs the root and API test suites and the web build
  on every push and pull request.
- **Community files.** `CONTRIBUTING.md` (licences per directory, DCO sign-off with
  `git commit -s`), `SECURITY.md` (private reporting to contact@krinea.org or through
  GitHub private vulnerability reporting), `CODE_OF_CONDUCT.md` (Contributor Covenant
  2.1) and `CITATION.cff` for release 0.1.0, which the site footer shows. One repository
  URL everywhere: https://github.com/aymardino/krinea. The energy template has 51
  fields, not 52.
- **Public pages.** The privacy policy, security page and terms describe the actual data
  flows: what each AI task sends, what Krinea stores, retention of sign-in links and
  sessions, and OVHcloud as e-mail processor.

**Why.** The merge silently reintroduced divergent copies of the engine and an outdated
README; the review then found security gaps that matter as soon as the service is public
(pre-registered accounts, a forgeable origin in e-mailed links, a development shortcut
that could leak sign-in links, placeholder secrets accepted in production), PDFs that
outlived their review, and documentation that no longer matched the code.

**Consequences.** Self-hosters upgrading must set a real `SECRET_KEY` and, on public
servers, `BASE_URL` and `PUBLIC_ORIGIN`. A password set on an account whose address was
never verified stops working at the first e-mail or Google sign-in. Undo: each item is a
separate commit and can be reverted on its own, though reverting the security items is
not advised.

### P-09 · Legal vehicle for a paid offer

Undecided; until then the hosted service stays free.

## D-29 · 2026-11-17 · decided · Which duplicate is kept; filters by imported file

**Decision.** When records are merged, the reviewer decides which one is kept, or the
review's rule does:

- **Source order.** A review can rank its databases (settings, "Preferred sources for
  duplicates", stored in `settings.source_priority`). The record from the source highest in
  the list is kept, then the most complete one, then the earliest import. A record ranks by
  its own source (the label given at import, otherwise the first source it lists), never by
  the sources it absorbed in an earlier merge. With no order saved, the rule is unchanged:
  the most complete record is kept.
- **Explicit choice on a pair.** Each pair to check offers "Keep this one" on both records
  (`POST /dedup/candidates/{id}/merge?keep={record_id}`), the record the rule would keep
  being marked as suggested; "Different, keep both" is unchanged.
- **Groups and chains.** Records certain to be the same study merge in one group whatever
  their number (union of the certain pairs, so A = B and B = C put A, B and C together). A near
  match of a record merged away, automatically or by hand, is asked about the kept record,
  once, with the best score found; a pair already answered stays answered.
- **Merging fills gaps.** The kept record keeps its own values; its empty fields are filled
  from the other records, and its sources list its own source first, then the others, so
  PRISMA counts every database the study was found in. Removed duplicates stay restorable.
- **Filter by file.** Screening and extraction lists filter by imported file
  (`import_id`). A record merged away from that file still counts for it through the
  record it was merged into. Extraction also filters by status and PDF, and "Extract with
  AI" then runs on the studies shown only.
- **AI runs stay inside the review.** Explicit `record_ids` sent to the screening or
  extraction runs are intersected with the review's own pool, and the job runners skip any
  record of another review.

## D-30 · 2026-11-17 · decided · Keywords per search; exact label filter

**Decision.** A review often runs one search per sub-question. Each imported file (one
search) can carry its own highlight keywords, stored in `criteria.search_keywords` by import
id and set with `PUT /imports/{import_id}/keywords` (administrators, like the review's own
keywords). They are highlighted in addition to the review's keywords on the records that
search found, a merged record getting the keywords of every search that found it (the record
lists them in `found_in`). The screening rail shows both lists when a file is selected.
Keywords stay shared by the team, so double screening shows everyone the same highlights,
and they remain a visual aid: eligibility criteria stay the review's own, and the AI does
not read them. Deleting an import deletes its keywords. Screening and extraction lists also
filter by label, matched exactly ("SQ1" does not match "SQ10").

## D-31 · 2026-11-17 · decided · Record kept by file order; merges can be undone

**Decision.** The review settings offer three rules for the record kept among duplicates:
the most complete one (default), the order of the imported files (for instance one file per
search query, the most reliable first; `settings.keeper_rule = "file"` with
`settings.file_priority`, a list of import ids), or the order of the databases (`"database"`,
`settings.source_priority`). Within a file or a database, the most complete record wins. A
review that saved a database order before the rule existed keeps using it.

Merges can be undone without loss. The first time a merge fills a record's gaps, its own
values are stored (`record_originals`). Restoring one duplicate recomputes the record it had
been merged into from those values and the duplicates still merged; "Restore all"
(`POST /dedup/restore-all`) brings every duplicate back and gives kept records their own
values back. Pairs answered "different" stay answered. Merges made before originals were
stored only get their list of sources put right. Deleting an import recomputes the records
that had absorbed its duplicates.

## D-32 · 2026-11-18 · decided · Pages follow background jobs; detection thresholds are kept

**Decision.** Duplicate detection, AI screening and AI extraction run in the worker in
production (`INLINE_JOBS=0`), so starting one answers at once with a queued job. The pages
now follow the job (`GET /jobs/{id}` every 1.5 seconds), show a progress bar, and refresh
their data and report the result only when it ends; a job already under way when a page
opens (after a reload, or started by a teammate) is found in `GET /reviews/{id}/jobs` and
followed too. Detection reports its progress (undoing the previous merges, comparing titles,
writing the merges) through a separate session, so the work itself stays one transaction;
SQLite allows one writer at a time, so there the bar only moves when the job ends. The worker,
once it has been up for two minutes, marks failed the jobs its previous instance left running
(a deploy or a crash stops it mid-job), so no page waits forever. The thresholds of the last
detection are saved in the review settings (`dedup_auto_threshold`, `dedup_review_threshold`,
between 50 and 100) and the sliders start from them.

**Why.** On the hosted service the page reported "0 duplicates removed" at once and showed
the new result only after a reload, with no sign that anything was running, and the
thresholds went back to 95 and 85 at every visit.

## D-33 · 2026-11-18 · decided · Screening queue filtered by several keywords; pasted keyword lists

**Decision.** A click on a highlight keyword in the screening rail adds it to the queue's
filter (a second click takes it out) instead of typing it into the search box. The filter
shows above the queue with a remove button per keyword, a choice between records that
mention all of them or at least one (`GET /records?kw=...&kw=...&kw_mode=all|any`), and
"Show all", which also clears the search box; the search box has its own clear button.
Keywords match as the counts in the rail count them (whole words, `*` as wildcard, title,
abstract and keywords), so a keyword shown with 90 records filters those 90. The keyword
fields take several keywords at once: commas, semicolons, tabs and line breaks separate
them, so a column pasted from a spreadsheet goes in as is, and the stored lists are split
the same way when read. Gemini calls are serialised, because its SDK keeps a single key
for the whole process and two users' calls made at once could otherwise swap keys.

**Why.** A pasted list became one long keyword, the only way back after a click on a
keyword was to empty the search box by hand, and two keywords could not be combined.

## D-34 · 2026-11-19 · decided · AI screening suggestions follow the queue on screen

**Decision.** "Ask the AI for suggestions" sends the records of the queue as shown (view,
file, label, keywords and search applied): its first records with neither a suggestion
nor the reviewer's decision, 50 at most per run. The AI panel says so, with the number.

**Why.** The run took the next 50 undecided records of the whole review in import order.
With a filter on, those were seldom the records on screen, so nothing seemed to happen.

## D-35 · 2026-11-19 · decided · Current Gemini models; AI runs say what went wrong

**Decision.** Gemini defaults move to `gemini-3.5-flash-lite` for screening and
`gemini-3.8-flash` for extraction, and Gemini is called through the maintained `google-genai`
SDK with one client per call (the key never goes into process-wide state, so the calls of
D-33 no longer need to be serialised). The output cap of a Gemini call is at least 8192
tokens, since its thinking counts against it, and no temperature is sent. A screening run
starts with the record on screen, then the next ones of the queue without a suggestion or
the reviewer's decision, going round to the top. A failure that every following record
would hit (key refused, model not available, quota, no credit) stops the run at once; a
rate limit is first waited out (the delay the provider asks for, one minute at most, three
times); five failures in a row stop it too. The job's result says what happened
(`error_kind`, the provider's message without the key, the model used) and the AI panel
keeps the reviewer's last run in words they can act on. The queue is fetched again each
time the run saves a suggestion, so each one shows as it comes, and the queue marks the
records that have one.

**Why.** Since 18 September 2026 Google opens the 2.5 models only to projects that used them
before: with a new key every call failed, the run reported 0 suggestions in a toast that
vanished, and the suggestions of a run that worked went to records above the one on screen.
Gemini's thinking could also use up the old 1024-token cap and leave an empty answer.

## D-36 · 2026-11-19 · decided · Screening queue in the order the reviewer picks

**Decision.** The screening queue has an order selector: import order (the default), title
A to Z or Z to A, year newest or oldest first, first author, journal, or the AI's
suggestion (include, most confident first, then maybe, then exclude, least confident
first). It is `GET /records?sort=...`, applied after every filter and before the page is
cut. Titles and names sort as one alphabetises them (accents, case and leading quotes
ignored); records without the value sorted on come last, and equal values keep the import
order. With an order other than import, the cursor is the last record of the previous page.

**Why.** The queue could only be read in import order.

## D-37 · 2026-11-19 · decided · Releases archived on Zenodo, with a changelog

**Decision.** Each GitHub release is archived by Zenodo, which gives it a DOI (one per
version, plus a concept DOI that always points to the latest). Zenodo copies its metadata
from `CITATION.cff`, which now carries the author's ORCID and affiliation. `CHANGELOG.md`
says what each version contains, and `codemeta.json` describes the software for HAL and
Software Heritage. The first release is v0.1.0, the version the site already shows (DOI
10.5281/zenodo.24380294; concept DOI 10.5281/zenodo.24380293).

**Why.** A DOI makes Krinea citable in articles and dates each version publicly; journals
for research software such as JOSS ask for tagged releases or a changelog.

**Consequences.** A new version changes the number everywhere it appears (`CITATION.cff`,
`codemeta.json`, `apps/api/pyproject.toml`, `apps/api/krinea_api/__init__.py`,
`packages/core/pyproject.toml`, `packages/core/krinea_core/__init__.py`,
`apps/web/package.json`, `apps/web/src/lib/site.ts`,
`apps/web/content/{en,fr}/about.md`, README), adds a `CHANGELOG.md` section, then gets a
tag and a GitHub release. Undo: switch the repository off in Zenodo; archived versions stay
online.

## D-38 · 2026-11-20 · decided · Gemini 3.8 Flash by default

**Decision.** New reviews use Google Gemini, and `gemini-3.8-flash` is the default model for
screening suggestions as well as extraction drafts (it replaces `gemini-3.5-flash-lite` for
screening, chosen in D-35). The default provider is `krinea_core.llm.DEFAULT_PROVIDER`; the
API reads it for the settings of a new review and for a review whose settings name no
provider, and the web app and the Streamlit edition repeat it. Existing reviews keep the
provider stored in their settings, and a model typed in the review settings still wins.

**Why.** One model for both tasks. Gemini 3.8 Flash is Google's current stable Flash model
(from 1 December 2026 Google answers `gemini-2.5-pro` requests with it), and Gemini's free
tier covers it, so a reviewer can try the AI with a free Google AI Studio key.

**Consequences.** Screening costs more per record than with Flash-Lite. Google's prices per
million tokens: 0.75 USD in and 3.75 USD out until 31 December 2026, then 1.50 and 7.50,
against 0.30 and 2.50 for `gemini-3.5-flash-lite`. A reviewer who prefers the cheaper model
types it in the review settings.

## D-39 · 2026-11-20 · decided · Exports of each stage, filtered; "No reason" in screening

**Decision.** A review has an Exports tab. It exports the records of a stage: title and
abstract screening (every unique record), full-text screening (the records kept at title and
abstract) or extraction (the studies included at full text). Filters: decision (included,
maybe, excluded, conflict, pending), exclusion reason (or excluded without one), PDF at full
text (on file, missing, not retrievable), imported file (a merged duplicate counts for every
file that found it) and label (exact match). The page shows how many records the file will
hold; formats are RIS, CSV and Excel. A screening export has one row per record, with its
status and reason at both stages, PDF, labels, notes and the files it was found in; the
reason is the one PRISMA counts (consensus first). The extraction export holds the verified
extractions, or every included study with the status of its extraction. API:
`GET /export/screening.{ris,csv,xlsx}`, `GET /export/extractions.{csv,xlsx,ris}` (with
`status`, `import_id`, `label`) and `GET /export/count`; the earlier export URLs still work.
Control characters that Excel refuses are dropped from Excel exports. In a blind review, a
member below admin gets only their own reasons and, in the decision log, only their own
decisions. The exclusion reason of the screening page has a "No reason" choice that empties
it.

**Why.** Exports were all or nothing, on the PRISMA page: the records kept after title and
abstract screening (to fetch the full texts) or the reports excluded at full text with their
reasons could only be had by filtering a full CSV by hand. The decision log gave a blind
reviewer the other reviewers' decisions. A reason chosen for an exclusion, or proposed by
the AI, could not be removed.

## D-40 · 2026-11-20 · decided · AI runs over the whole list; lists read 200 at a time

**Decision.** The AI panel of a screening page picks how many records a run takes: 50, 200,
500 or the whole list. The server reads them from the list as the page shows it (view, file,
label, keywords, search and order; `queue` in `POST /ai/screen`), whole and not only the
records the page has loaded: from the record on screen, down the list and round to the top,
without the records the reviewer decided and, unless "redo" is ticked, without those that
already have a suggestion (a redo replaces them). `POST /ai/screen/preview` says how many
records of the list a run can take and how many the next one takes; the panel shows both, and
a run of more than 500 records asks first. A run goes back in line every 50 records
(`Requeue` in `services/jobs.py`), so that the jobs queued meanwhile, anybody's, do not wait
for its end; when jobs run inline, the turns follow each other at once. The screening list is
read 200 records at a time (`GET /records?offset=`): Next and Previous go on to the next or
previous 200 at the ends of the list, as do links at both ends. The list can also be ordered
with the AI's exclusions first (`sort=ai_exclude`): exclude, the surest first, then maybe,
then include, the least sure first; records without a suggestion last.

**Why.** A run took 50 records at most, chosen among the 200 the page had loaded: once these
had a suggestion, the panel said there was nothing left to do although thousands of records
had none, and the list could not be read past its 200th record. A suggestion could not be
made again after a change of criteria or model. With a single worker (D-17), a run over
thousands of records would have held up every other job for hours.

## D-41 · 2026-11-20 · decided · Export filters take several values

**Decision.** The filters of the Exports tab (D-39) are lists to tick: decision, exclusion
reason, PDF, imported file and label each take several values. A record passes when it
matches any value ticked in a filter, and every filter used. The reason filter shows when the
exclusions are part of the export (no decision filter, or "Excluded" ticked) and keeps the
records excluded for one of the reasons ticked ("No reason given": excluded without one). The
API takes repeated parameters (`?import_id=a&import_id=b`); a single value works as before.

**Why.** The records of two searches, or the exclusions for two reasons, took two files to
merge by hand.
