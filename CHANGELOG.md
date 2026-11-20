# Changelog

What each version of Krinea contains, newest first. Version numbers follow
[semantic versioning](https://semver.org); every GitHub release is archived on
Zenodo with its own DOI.

## [Unreleased]

- **AI.** The AI panel takes any number of records per run, from the record
  on screen (one by default at full text, 50 at title and abstract) up to the
  whole list, and can redo the suggestions already made. A run follows the
  whole list as filtered and ordered, not only the records loaded on the page,
  and a long run lets other jobs through every 50 records.
- **Screening.** The list goes past its first 200 records, and it can be
  ordered with the AI's exclusions first.
- **Exports.** Each filter takes several values: several files, decisions,
  reasons, labels or PDF states at once.
- **Files.** When duplicates are kept by the order of the imported files, each
  study belongs only to the file of the record kept: file filters, AI runs,
  keywords of each search and exports follow it. Screening exports gain a
  `file` column.

## [0.2.0] - 2026-11-20

- **AI.** New reviews use Google Gemini, with `gemini-3.8-flash` for screening
  suggestions and extraction drafts. Existing reviews keep their settings.
- **Exports.** A new Exports tab exports the records of each stage (title and
  abstract, full text, extraction) as RIS, CSV or Excel, filtered by decision,
  exclusion reason, PDF, imported file and label, with the number of records
  shown first.
- **Screening.** The exclusion reason has a "No reason" choice that empties it.
- **Fixed.** In a blind review, the decision log export no longer shows a
  reviewer the other reviewers' decisions.

## [0.1.0] - 2026-11-19

First archived release, the version running on krinea.org. DOI:
[10.5281/zenodo.24380294](https://doi.org/10.5281/zenodo.24380294).

- **Accounts and teams.** Sign-in with a password, an e-mail link or Google;
  reviews with roles and e-mail invitations.
- **Imports.** RIS, BibTeX, PubMed, Web of Science, CSV and Excel exports;
  duplicate detection with candidates to review.
- **Screening.** Title/abstract and full-text screening, blind double
  screening with conflicts and consensus, keyboard shortcuts, highlighted
  keywords, and a queue that can be ordered by title, year, first author,
  journal or AI suggestion.
- **AI assistance.** Screening suggestions and extraction drafts run as
  background jobs on Anthropic Claude, Google Gemini or DeepSeek models, with
  the reviewer's own key or included credits. A run waits out rate limits,
  stops on errors it cannot recover from (key refused, model unavailable,
  quota or credit exhausted) and says what went wrong.
- **Extraction.** Forms defined by the review authors; the AI fills each field
  with a verbatim quote, the reviewer verifies it beside the PDF, and the AI's
  values are kept next to the verified ones.
- **Full texts.** PDF upload and open-access lookup through Unpaywall.
- **Reporting.** PRISMA 2020 flow diagram and exports.
- **Interface.** English and French.
- **Engine.** `krinea_core` (MIT licence): parsers, deduplication, screening
  logic, extraction forms, LLM calls with usage, PDF text, PRISMA 2020 SVG
  renderer.
- **Streamlit edition.** The original single-user application
  (`review_app.py`), on the same engine.

[Unreleased]: https://github.com/aymardino/krinea/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/aymardino/krinea/releases/tag/v0.2.0
[0.1.0]: https://github.com/aymardino/krinea/releases/tag/v0.1.0
