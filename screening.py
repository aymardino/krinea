"""Compatibility shim: this module now lives in packages/core as krinea_core.screening."""
import sys as _sys
import krinea_core.screening as _m
_sys.modules[__name__] = _m
