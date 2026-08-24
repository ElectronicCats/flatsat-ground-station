#!/usr/bin/env python3
"""FlatSat Host CLI launcher.

Entry point so the CLI can be run as `./flatsat_cli.py ...` instead of
`python -m cli ...`. The implementation lives in the `cli` package.
"""

import sys
from pathlib import Path

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in terminals with legacy code pages
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli.app import main  # noqa: E402

if __name__ == "__main__":
    main()
