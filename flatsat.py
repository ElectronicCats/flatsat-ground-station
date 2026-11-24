#!/usr/bin/env python3
"""FlatSat Host CLI launcher.
1-to-1 parity with CatSniffer-Tools / catnip (catnip.py).

The launcher is also a bootstrapper: if the CLI dependencies (click, rich,
pyserial, pycryptodome) are missing it creates a local virtual environment,
installs requirements-app.txt and re-executes itself with that interpreter.
That way `python flatsat.py devices` works on a clean checkout.
"""

import os
import sys
from pathlib import Path

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules.utils.bootstrap import (  # noqa: E402
    BOOTSTRAP_ENV,
    CLI_MODULES,
    ensure_environment,
    err,
    relaunch,
)


def _bootstrap_if_needed() -> None:
    """Make sure the CLI dependencies are available, then re-exec if needed."""
    if getattr(sys, "frozen", False) or os.environ.get(BOOTSTRAP_ENV):
        return

    import importlib.util

    missing = []
    for name in CLI_MODULES:
        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(name)
    if not missing:
        return

    script = Path(__file__).resolve()
    try:
        python = ensure_environment(
            modules=CLI_MODULES,
            requirements_file=script.parent / "requirements-app.txt",
            project_root=script.parent,
            label="El CLI",
        )
    except RuntimeError as exc:
        err(f"No se pudo preparar el entorno: {exc}")
        raise SystemExit(1) from None
    relaunch(python, script, sys.argv[1:])


if __name__ == "__main__":
    _bootstrap_if_needed()

    from modules.core.cli import main_cli

    main_cli()
