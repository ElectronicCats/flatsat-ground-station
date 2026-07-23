"""Backward-compatible re-export.

RadioBridge moved to `core/radio_bridge.py` so the webapp and the CLI share the
same RF transmit path. Existing imports (`from webapp.radio_bridge import
RadioBridge`) keep working through this shim.
"""

from core.radio_bridge import RadioBridge

__all__ = ["RadioBridge"]
