"""Backward-compatibility shim package for cli.

DEPRECATED: every name here forwards to `modules.*`. Add new code under
`modules/` instead — see cli/COLLABORATE.md.
"""
import importlib
import os
import sys
import warnings

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
    except Exception as _exc:  # surfaced instead of silently dropping the alias
        warnings.warn(
            f"cli.{_short} could not forward to {_target_name}: {_exc}",
            RuntimeWarning,
            stacklevel=2,
        )

def _re_export(target, skip=()):
    """Copy a module's public names into this package's namespace."""
    names = getattr(target, "__all__", dir(target))
    globals().update(
        {k: getattr(target, k) for k in names if not k.startswith("__") and k not in skip}
    )


_re_export(_target_cli, skip=("cli",))
_re_export(_target_session)

__path__ = [os.path.dirname(__file__)]
