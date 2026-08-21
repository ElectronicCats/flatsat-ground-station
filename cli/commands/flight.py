"""Backward-compatibility shim for flight command module."""

from modules.core.cli import _detect_local_role, flight

__all__ = ["_detect_local_role", "flight"]
