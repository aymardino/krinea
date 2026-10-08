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

## D-13 · 2026-10-08 · proposed · Licence

**Current state.** A permissive MIT licence file was added to the repository
when the README was written. This should be confirmed or changed before the
repository goes public.

**Recommendation.** AGPL-3.0 for the application (anyone may self-host and
modify it, but a company offering it as a hosted service must publish its
changes), keeping the reusable core modules (parsers, dedup) under MIT so
other tools can embed them. This is the standard "open core + hosted
service" pattern (Plausible, Cal.com, Nextcloud) and protects a paid hosted
offer without closing the code.

---

## Proposed decisions (waiting for the owner)

### P-01 · Product name and domain

Shortlist to check on a registrar (the session's network cannot query domain
registries): **Scrinium** (Latin: the box that held scrolls; .app/.io),
**Sieva** (sieve; .app/.io), **Tamis** (French for sieve, reads well in
English; .app), **LitSieve** (.com/.app). Pick one, check `.com` + `.app`
availability and trademark collisions (no clash with Rayyan, Covidence,
DistillerSR, EPPI-Reviewer, Colandr, ASReview, SysRev, Nested Knowledge,
PICO Portal, Elicit).

### P-02 · Business model

Recommendation: fully open source (D-13) + a hosted service with three
tiers: **Free** (self-host or hosted with limits: 1 active review, 2
collaborators, bring-your-own AI key), **Pro** (unlimited reviews, team
features, priority support, included AI credits), **Institution** (SSO,
admin console, invoicing, data residency). Free for reviewers in low-income
countries, as Covidence does. Rayyan's published tiers (Free / Essential /
Advanced individual; Academic / Business / Enterprise institutional) and
Covidence's per-review pricing (USD 339 per review per year) are the
reference points.

### P-03 · AI access: bring-your-own-key and included credits

Recommendation: both. BYOK is always available (self-hosted and Free tier):
the key is stored encrypted per user, never logged. Paid tiers include a
monthly AI budget billed at provider cost plus margin, with a visible meter.
This keeps the free edition useful without the project paying for inference.

### P-04 · Product architecture

Recommendation: monorepo with `apps/api` (Python, FastAPI, SQLAlchemy,
PostgreSQL, background worker for imports/dedup/AI batches/PDF processing),
`apps/web` (Next.js + TypeScript + Tailwind, marketing site and application,
en/fr), `packages/core` (the existing Python modules). Accounts with
email + password, magic link, Google and ORCID sign-in. PDFs in an
S3-compatible bucket (Cloudflare R2 or Backblaze B2). Billing with Stripe.

### P-05 · Design

Recommendation: a design system (tokens, typography, components) built with
shadcn/ui; application layout modelled on the owner's Rayyan screenshots
(top tabs, list + detail screening view, filter rail with keyword counts,
overview dashboard with summary cards and progress donut), plus keyboard
shortcuts (I / M / E, arrows).

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
