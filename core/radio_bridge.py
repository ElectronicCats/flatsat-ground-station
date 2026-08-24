"""Backward-compatibility shim for core.radio_bridge -> modules.core.radio_bridge."""
import sys
import importlib

_target = importlib.import_module("modules.core.radio_bridge")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target
