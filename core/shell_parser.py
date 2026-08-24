"""Backward-compatibility shim for core.shell_parser -> modules.core.shell_parser."""
import sys
import importlib

_target = importlib.import_module("modules.core.shell_parser")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target
