"""Backward-compatibility shim package for cli."""
import os
import sys
import importlib

_target_cli = importlib.import_module("modules.core.cli")
_target_session = importlib.import_module("modules.core.session")

_submodules = {
    "app": "modules.core.cli",
    "cli": "modules.core.cli",
    "session": "modules.core.session",
    "_version": "modules.utils._version",
}

for _short, _target_name in _submodules.items():
    try:
        _mod = importlib.import_module(_target_name)
        sys.modules[f"cli.{_short}"] = _mod
        globals()[_short] = _mod
    except Exception:
        pass

globals().update({k: getattr(_target_cli, k) for k in getattr(_target_cli, "__all__", dir(_target_cli)) if not k.startswith("__") and k != "cli"})
globals().update({k: getattr(_target_session, k) for k in getattr(_target_session, "__all__", dir(_target_session)) if not k.startswith("__")})

__path__ = [os.path.dirname(__file__)]
