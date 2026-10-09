"""
krinea_core — the reusable heart of Krinea (MIT licensed).

Bibliographic parsers and writers (biblio), duplicate detection (dedup),
screening logic (screening) and author-defined extraction forms
(extraction_schema). No web framework, no database: plain Python functions
that any review tool can embed.
"""
from krinea_core import biblio, dedup, extraction_schema, screening  # noqa: F401

__version__ = "0.1.0"
__all__ = ["biblio", "dedup", "extraction_schema", "screening"]
