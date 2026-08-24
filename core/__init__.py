"""Backward-compatibility shim for core -> modules.core."""
import sys
import importlib

_target = importlib.import_module("modules.core")
sys.modules[__name__] = _target
sys.modules["core"] = _target

_submodules = [
    "ccsds",
    "cli",
    "constants",
    "device",
    "radio_bridge",
    "serial_manager",
    "session",
    "shell_parser",
    "state",
    "telecommand",
    "telemetry",
]

for _sub in _submodules:
    try:
        _mod = importlib.import_module(f"modules.core.{_sub}")
        sys.modules[f"core.{_sub}"] = _mod
        setattr(_target, _sub, _mod)
    except Exception:
        pass

globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
