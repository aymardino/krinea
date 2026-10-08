"""Compatibility shim: this module now lives in packages/core as tamis_core.dedup."""
import sys as _sys
import tamis_core.dedup as _m
_sys.modules[__name__] = _m
