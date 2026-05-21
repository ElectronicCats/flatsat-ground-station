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

            # AUTOMATIC SWITCHING LOGIC:
            # 1. Always transmit on Radio 1 (Telecommand) as that is sintonized to 916 MHz where the satellite listens
            tx_radio = 1
            
            try:
                # Switch physical board to radio1 antenna and clear buffers
                self._state.active_radio = tx_radio
                self._state.device.send_shell_command_full("radio1")
                self._state.device.reset_radio_input_buffers()
                
                # Try sending using command mode TX first
                resp = self._state.device.send_radio_tx(tx_radio, data)
                if resp is not None:
                    if "Success" in resp:
                        status_dict = {"status": "sent", "bytes": len(data), "response": resp}
                    else:
                        status_dict = {"status": "error", "error": resp}
                else:
                    # Fallback to stream/raw transmission on active radio
                    if self._state.device.send_radio_raw(tx_radio, data):
                        status_dict = {"status": "sent", "bytes": len(data), "response": "Stream TX Success"}
                    else:
                        status_dict = {"status": "error", "error": f"No radio available on Radio {tx_radio}"}
            except Exception as e:
                status_dict = {"status": "error", "error": str(e)}
            finally:
                # 2. Always revert back to Radio 0 (Telemetry RX) to listen for downlinks on 915 MHz
                self._state.active_radio = 0
                self._state.device.send_shell_command_full("radio0")
                self._state.device.reset_radio_input_buffers()
                
            return status_dict

        return {"status": "sent_simulated", "bytes": len(data), "data_hex": data.hex()}

    def send_tc(self, apid: int, payload: bytes) -> dict:
        """Build CCSDS TC frame and send."""
        frame = build_tc(apid, payload)
        result = self.send_raw(frame)
        result["frame_hex"] = frame.hex()
        return result
