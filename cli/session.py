"""Backward-compatibility shim for cli.session -> modules.core.session.

DEPRECATED: forwards to `modules.core.session`. Add new code under `modules/`,
not here — see cli/COLLABORATE.md.
"""
import importlib
import sys

_target = importlib.import_module("modules.core.session")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target
