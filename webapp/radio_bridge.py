"""Radio bridge: sync wrapper over core for Flask.

Uses real FlatSatDevice when connected, simulated mode otherwise.
This file is the pivot target for GS-08 (kill chain).
"""

from core.ccsds import build_tc


class RadioBridge:
    """Sync serial bridge to FlatSat."""

    def __init__(self, gs_state):
        self._state = gs_state

    @property
    def is_connected(self) -> bool:
        return self._state.is_hardware and self._state.device is not None

    @property
    def mode(self) -> str:
        return "hardware" if self.is_connected else "simulated"

    def send_raw(self, data: bytes) -> dict:
        """Send raw bytes to satellite."""
        if self.is_connected and self._state.device:
            try:
                ok = self._state.device.send_raw(data)
                if ok:
                    return {"status": "sent", "bytes": len(data)}
                return {"status": "error", "error": "send_raw failed"}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        return {"status": "sent_simulated", "bytes": len(data), "data_hex": data.hex()}

    def send_tc(self, apid: int, payload: bytes) -> dict:
        """Build CCSDS TC frame and send."""
        frame = build_tc(apid, payload)
        result = self.send_raw(frame)
        result["frame_hex"] = frame.hex()
        return result
