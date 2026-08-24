"""Radio bridge: synchronous RF transmit path shared by the webapp and CLI.

Uses a real FlatSatDevice when connected, simulated mode otherwise. Lives in
`core/` so both the Flask webapp and the `flatsat` CLI transmit telecommands
through the exact same code path (dual/single radio switching, command-mode TX
with stream fallback, and reverting to telemetry RX afterwards).
"""

from modules.core.ccsds import build_tc


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
            has_radio1 = getattr(self._state.device, "has_radio1", True)
            active_radio = getattr(self._state, "active_radio", 2)

            # Use dual mode ONLY if device actually has radio1 and active_radio permits dual mode.
            use_dual = has_radio1 and (active_radio == 2 or active_radio not in (0, 1))

            if use_dual:
                # DUAL RADIO MODE:
                # Transmit on Radio 1 (Telecommand @ 916 MHz) while telemetry keeps
                # coming in on Radio 0 (915 MHz). We must NOT touch self.active_radio
                # here: it is the user's persistent selection, and the background RX
                # loop plus the UI both read it. Repurposing it as a transient TX
                # target makes the RX loop switch to Radio 1 (losing telemetry),
                # contend with this TX on the Radio 1 lock (corrupting the command),
                # and — since the restore is not atomic — can leave it stuck on
                # Radio 1. Instead, serialize the transmit with radio_tx_lock and
                # flag tx_in_progress so the RX loop pauses for the brief TX window.
                tx_radio = 1
                with self._state.radio_tx_lock:
                    self._state.tx_in_progress = True
                    try:
                        # Switch physical board to radio1 antenna, set command mode and clear buffers
                        self._state.device.send_shell_command_full("radio1")
                        self._state.device.send_shell_command_full("lora_mode R1 command")
                        self._state.device.send_shell_command_full("lora_apply R1")
                        self._state.device.reset_radio_input_buffers()

                        # Try sending using command mode TX first
                        resp = self._state.device.send_radio_tx(tx_radio, data)
                        if resp is not None:
                            if not isinstance(resp, str):
                                resp = str(resp)
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
                        # Always revert Radio 1 to stream mode and switch back to Radio 0
                        # (Telemetry RX) so downlinks on 915 MHz keep arriving.
                        self._state.device.send_shell_command_full("lora_mode R1 stream")
                        self._state.device.send_shell_command_full("lora_apply R1")
                        self._state.device.send_shell_command_full("radio0")
                        self._state.device.reset_radio_input_buffers()
                        self._state.tx_in_progress = False
            else:
                # SINGLE RADIO MODE (CatSniffer/GS-only or manual override of specific radio):
                # On a single-radio board TX and RX share one physical radio, so the
                # RX loop must pause while we flip it into command mode and back.
                tx_radio = 1 if (has_radio1 and active_radio == 1) else 0
                with self._state.radio_tx_lock:
                    self._state.tx_in_progress = True
                    try:
                        # Keep selected radio and switch to it physically
                        r_str = f"R{tx_radio}"
                        self._state.device.send_shell_command_full(f"radio{tx_radio}")
                        self._state.device.send_shell_command_full(f"lora_mode {r_str} command")
                        self._state.device.send_shell_command_full(f"lora_apply {r_str}")
                        self._state.device.reset_radio_input_buffers()

                        # Try sending using command mode TX first
                        resp = self._state.device.send_radio_tx(tx_radio, data)
                        if resp is not None:
                            if not isinstance(resp, str):
                                resp = str(resp)
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
                        # Always revert selected Radio back to stream mode to listen for telemetry
                        r_str = f"R{tx_radio}"
                        self._state.device.send_shell_command_full(f"lora_mode {r_str} stream")
                        self._state.device.send_shell_command_full(f"lora_apply {r_str}")
                        self._state.device.reset_radio_input_buffers()
                        self._state.tx_in_progress = False

            return status_dict

        return {"status": "sent_simulated", "bytes": len(data), "data_hex": data.hex()}

    def send_tc(self, apid: int, payload: bytes) -> dict:
        """Build CCSDS TC frame and send."""
        frame = build_tc(apid, payload)
        result = self.send_raw(frame)
        result["frame_hex"] = frame.hex()
        return result
