"""Backward-compatibility shim for webapp.app -> modules.webapp.app."""
import sys
import importlib

_target = importlib.import_module("modules.webapp.app")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target

if __name__ == "__main__":
    _target.main()
