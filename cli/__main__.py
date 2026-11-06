#!/usr/bin/env python3

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

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Add vendor directory to sys.path for bundled dependencies
vendor_path = os.path.join(os.path.dirname(__file__), "vendor")
if os.path.exists(vendor_path):
    sys.path.insert(0, vendor_path)

# Internal (imported after sys.path is prepared above, so E402 does not apply)
from cli.app import main  # noqa: E402

if __name__ == "__main__":
    main()
