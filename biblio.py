"""Compatibility shim: this module now lives in packages/core as krinea_core.biblio."""
import sys as _sys
import krinea_core.biblio as _m
_sys.modules[__name__] = _m
