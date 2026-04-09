"""Radio bridge: sync wrapper over core for Flask.

In hardware mode, sends raw bytes via serial to FlatSat.
In simulated mode, logs the command and returns success.
This file is the pivot target for GS-08 (kill chain).
"""

from core.ccsds import build_tc
from core.state import GroundStationState

_state = GroundStationState()


class RadioBridge:
    def __init__(self):
        self._state = _state

    @property
    def is_connected(self) -> bool:
        return not self._state.is_simulated

    @property
    def mode(self) -> str:
        return "hardware" if self.is_connected else "simulated"

    def send_raw(self, data: bytes) -> dict:
        if self.is_connected and self._state.device:
            try:
                self._state.device.send_raw(data)
                return {"status": "sent", "bytes": len(data)}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        return {"status": "sent_simulated", "bytes": len(data), "data_hex": data.hex()}

    def send_tc(self, apid: int, payload: bytes) -> dict:
        frame = build_tc(apid, payload)
        result = self.send_raw(frame)
        result["frame_hex"] = frame.hex()
        return result
