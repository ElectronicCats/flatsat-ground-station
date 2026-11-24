"""Backward-compatibility shim for flight command module.

DEPRECATED: forwards to `modules.core.cli`. Add new code under `modules/`,
not here — see cli/COLLABORATE.md.
"""

from modules.core.cli import _detect_local_role, flight

__all__ = ["_detect_local_role", "flight"]
