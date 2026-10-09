"""Compatibility shim: this module now lives in packages/core as krinea_core.extraction_schema."""
import sys as _sys
import krinea_core.extraction_schema as _m
_sys.modules[__name__] = _m
