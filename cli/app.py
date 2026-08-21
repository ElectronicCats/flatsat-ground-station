"""Backward-compatibility shim for cli.app -> modules.core.cli."""
import sys
import importlib

_target = importlib.import_module("modules.core.cli")
globals().update({k: getattr(_target, k) for k in getattr(_target, "__all__", dir(_target)) if not k.startswith("__")})
sys.modules[__name__] = _target

if __name__ == "__main__":
    _target.main()
