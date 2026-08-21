#!/usr/bin/env python3
"""FlatSat Host CLI launcher.
1-to-1 parity with CatSniffer-Tools / catnip (catnip.py).
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

from modules.core.cli import main_cli

if __name__ == "__main__":
    main_cli()
