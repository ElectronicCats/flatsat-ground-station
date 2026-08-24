"""Backward-compatibility shim for core.ccsds -> modules.core.ccsds."""
import sys
import importlib

_target = importlib.import_module("modules.core.ccsds")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target
