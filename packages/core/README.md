# krinea-core

The reusable, framework-free engine of [Krinea](../../README.md), MIT licensed
(`LICENSE` in this directory; the rest of the repository is AGPL-3.0-only). No web
framework, no database: plain Python functions that any review tool can embed. Both the
Krinea API and the Streamlit edition use it.

| Module | What it does |
|---|---|
| `krinea_core.biblio` | Parsers for RIS, BibTeX, PubMed/MEDLINE, Web of Science, CSV/TSV and Excel exports, normalised to one record dict; RIS and CSV writers |
| `krinea_core.dedup` | Duplicate detection (same DOI, identical normalised title, fuzzy title with year and first-author corroboration), clustering, choice of the most complete record, merging |
| `krinea_core.screening` | Multi-reviewer consensus, keyword highlighting, the AI screening prompt and the parsing of its answer |
| `krinea_core.extraction_schema` | Author-defined extraction forms: validation, JSON/CSV import and export, the AI prompt, cleaning of the answer, consistency checks, the energy-modelling template |
| `krinea_core.llm` | One `call_json` function for Anthropic (Claude), Google (Gemini) and DeepSeek that returns parsed JSON and token usage |
| `krinea_core.prisma` | PRISMA 2020 flow diagram as SVG, following the four official templates (new or updated review, with or without other sources), in English or French |
| `krinea_core.pdftext` | Plain text of a PDF (PyMuPDF), keeping the head and the tail of very long papers |
| `krinea_core.unpaywall` | Open-access PDF lookup by DOI through Unpaywall (needs a contact e-mail) |
| `krinea_core/data/` | `energy_template.json` (the 51-field energy-modelling extraction template) and `prisma2020_templates.json` (layout and wording of the official PRISMA 2020 templates, reproduced under CC BY 4.0 from prisma-statement.org) |

## Install

```bash
pip install -e packages/core                  # parsers, dedup, screening, forms, PRISMA, PDF text
pip install -e "packages/core[excel]"         # + Excel import (openpyxl)
pip install -e "packages/core[llm]"           # + provider SDKs for krinea_core.llm
pip install -e "packages/core[excel,llm]"     # what the API and the Streamlit edition install
```

The base install depends on `rapidfuzz`, `pandas` and `pymupdf`. The provider SDKs
(`anthropic`, `openai` for DeepSeek, `google-generativeai`) are an optional extra:
`krinea_core.llm` imports them lazily, only when a call is made, so every other module,
and `llm` itself, imports without them. Install the `llm` extra before making AI calls.

```python
from krinea_core import biblio, dedup

records = biblio.parse_file("search.ris", open("search.ris", "rb").read())
pairs = dedup.find_duplicates(records)
```

## Licence

MIT. Contributions to this directory are accepted under the MIT licence; see
`CONTRIBUTING.md` at the repository root.
