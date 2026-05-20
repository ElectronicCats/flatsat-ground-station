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
        """Send raw bytes to satellite via Radio 1 TX command, or fallback to Radio 0 stream."""
        if self.is_connected and self._state.device:
            # Check for CTF level win conditions to trigger LED feedback
            diff = getattr(self._state, "difficulty", 1)
            try:
                if diff == 1 and b"TEST" in data:
                    self._state.device.send_shell_command("color 0 50 0") # Green
                elif diff == 2 and b"\x08\x01\xc0" in data:
                    self._state.device.send_shell_command("color 0 0 50") # Blue
                elif diff == 3 and b"DIAG_MEM" in data:
                    self._state.device.send_shell_command("color 50 0 50") # Purple
            except Exception:
                pass

            try:
                # Try Radio 1 (Command mode) first if available
                resp = self._state.device.send_radio1_tx(data)
                if resp is not None:
                    if "Success" in resp:
                        return {"status": "sent", "bytes": len(data), "response": resp}
                    return {"status": "error", "error": resp}
                
                # Fallback to Radio 0 (Stream mode) for GS-only boards
                if hasattr(self._state.device, 'send_radio0_raw') and self._state.device.send_radio0_raw(data):
                    return {"status": "sent", "bytes": len(data), "response": "Stream TX Success"}
                
                return {"status": "error", "error": "No radio available for TX"}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        return {"status": "sent_simulated", "bytes": len(data), "data_hex": data.hex()}

    def send_tc(self, apid: int, payload: bytes) -> dict:
        """Build CCSDS TC frame and send."""
        frame = build_tc(apid, payload)
        result = self.send_raw(frame)
        result["frame_hex"] = frame.hex()
        return result
