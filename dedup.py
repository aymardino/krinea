"""Compatibility shim: this module now lives in packages/core as krinea_core.dedup."""
import sys as _sys
import krinea_core.dedup as _m
_sys.modules[__name__] = _m
