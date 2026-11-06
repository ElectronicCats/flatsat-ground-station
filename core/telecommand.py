"""Backward-compatibility shim for core.telecommand -> modules.core.telecommand."""
import importlib
import sys

_target = importlib.import_module("modules.core.telecommand")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target
