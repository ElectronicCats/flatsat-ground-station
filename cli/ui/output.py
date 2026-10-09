"""Backward-compatibility shim for cli.ui.output -> modules.utils.output.

DEPRECATED: forwards to `modules.utils.output`. Add new code under `modules/`,
not here — see cli/COLLABORATE.md.
"""
import importlib
import sys

_target = importlib.import_module("modules.utils.output")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target
