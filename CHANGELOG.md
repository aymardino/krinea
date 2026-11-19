# Changelog

What each version of Krinea contains, newest first. Version numbers follow
[semantic versioning](https://semver.org); every GitHub release is archived on
Zenodo with its own DOI.

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

[0.1.0]: https://github.com/aymardino/krinea/releases/tag/v0.1.0
