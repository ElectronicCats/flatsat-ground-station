"""Backward-compatibility shim for core.constants -> modules.core.constants."""
import sys
import importlib

_target = importlib.import_module("modules.core.constants")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target
