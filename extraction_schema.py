"""Compatibility shim: this module now lives in packages/core as tamis_core.extraction_schema."""
import sys as _sys
import tamis_core.extraction_schema as _m
_sys.modules[__name__] = _m
