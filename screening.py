"""Compatibility shim: this module now lives in packages/core as tamis_core.screening."""
import sys as _sys
import tamis_core.screening as _m
_sys.modules[__name__] = _m
