"""
_version.py - Version reader for FlatSat Ground Station CLI
"""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def get_version() -> str:
    try:
        return version("flatsat-ground-station")
    except PackageNotFoundError:
        # Fallback for editable / local dev tree without installation
        version_file = Path(__file__).resolve().parent.parent / "VERSION"
        if version_file.is_file():
            return version_file.read_text(encoding="utf-8").strip()
    return "1.0.0"


__version__ = get_version()
