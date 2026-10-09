# krinea-core

The reusable, framework-free core of [Krinea](../../README.md), MIT licensed:

- `krinea_core.biblio` — RIS, BibTeX, PubMed, Web of Science, CSV/Excel parsers; RIS/CSV writers
- `krinea_core.dedup` — DOI / exact-title / fuzzy-title duplicate detection, clustering, merging
- `krinea_core.screening` — multi-reviewer consensus, keyword highlighting, AI screening prompt
- `krinea_core.extraction_schema` — author-defined extraction fields: prompt, cleaning, checks

```bash
pip install -e packages/core
python -c "from krinea_core import biblio; print(biblio.parse_file('x.ris', open('x.ris','rb').read())[0])"
```

The LLM calls themselves live in the application (`extractor.py`), so this
package has no provider SDK dependency.
