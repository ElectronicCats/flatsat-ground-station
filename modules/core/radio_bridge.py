"""Radio bridge: synchronous RF transmit path shared by the webapp and CLI.

Uses a real FlatSatDevice when connected, simulated mode otherwise. Lives in
`core/` so both the Flask webapp and the `flatsat` CLI transmit telecommands
through the exact same code path (dual/single radio switching, command-mode TX
with stream fallback, and reverting to telemetry RX afterwards).
"""

import re
import time

from modules.core.ccsds import build_tc
from modules.core.constants import (
    LORA_DOWNLINK_HZ,
    LORA_SYNCWORD_TX,
    LORA_TX_SETTLE_S,
    LORA_UPLINK_HZ,
)


class RadioBridge:
    """Sync serial bridge to FlatSat."""

    def __init__(self, gs_state):
        self._state = gs_state

    def _read_syncword(self, radio_idx: int) -> str | None:
        """Read the sync word currently configured on a radio ('public'/'private'/'0xNN')."""
        resp = self._state.device.send_shell_command_full(f"lora_config R{radio_idx}", timeout=2.0)
        if not isinstance(resp, str):
            return None
        m = re.search(r"Sync Word:\s*(Public|Private)\b", resp, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        m = re.search(r"Sync Word:\s*(0x[0-9A-Fa-f]+)", resp)
        return m.group(1) if m else None

    def _prepare_tx(self, radio_idx: int) -> None:
        """Put a radio into a coherent uplink-TX configuration.

        Frequency, mode *and* sync word all have to agree with the target
        board. Skipping the sync word is the classic failure: Radio 1 ships on
        the private sync word while the satellite listens on the public one, so
        every telecommand is transmitted, reported as a success, and then
        silently discarded by the receiver.
        """
        r = f"R{radio_idx}"
        self._state.device.send_shell_command_full(f"radio{radio_idx}")
        self._state.device.send_shell_command_full(f"lora_syncword {r} {LORA_SYNCWORD_TX}")
        self._state.device.send_shell_command_full(f"lora_freq {r} {LORA_UPLINK_HZ}")
        self._state.device.send_shell_command_full(f"lora_mode {r} command")
        self._state.device.send_shell_command_full(f"lora_apply {r}")
        self._state.device.reset_radio_input_buffers()

    def _restore_rx(self, radio_idx: int, syncword: str | None = None) -> None:
        """Return a radio to stream mode after a transmit. Never raises."""
        r = f"R{radio_idx}"
        # Allow the LoRa PHY to finish pushing the packet out over the air
        # before re-tuning the synthesizer back to the downlink frequency.
        time.sleep(LORA_TX_SETTLE_S)
        for cmd in (
            f"lora_syncword {r} {syncword}" if syncword else None,
            f"lora_freq {r} {LORA_DOWNLINK_HZ}",
            f"lora_mode {r} stream",
            f"lora_apply {r}",
        ):
            if cmd:
                try:
                    self._state.device.send_shell_command_full(cmd)
                except Exception:
                    pass
        try:
            self._state.device.send_shell_command_full("radio0")
        except Exception:
            pass
        self._state.device.reset_radio_input_buffers()

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

            # Use dual mode whenever device has radio1 (CatSniffer GS), ensuring
            # telecommands/attacks are ALWAYS transmitted on Radio 1 (the 916 MHz Uplink TX radio).
            use_dual = has_radio1

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
            else:
                # SINGLE RADIO MODE (CatSniffer/GS-only or manual override of specific radio):
                # On a single-radio board TX and RX share one physical radio, so the
                # RX loop must pause while we flip it into command mode and back.
                tx_radio = 1 if has_radio1 else 0

            with self._state.radio_tx_lock:
                self._state.tx_in_progress = True
                prev_syncword = None
                try:
                    # Remember the operator's sync word so the radio is handed
                    # back exactly as we found it after the transmit window.
                    prev_syncword = self._read_syncword(tx_radio)
                    self._prepare_tx(tx_radio)

                    # Try sending using command mode TX first
                    resp = self._state.device.send_radio_tx(tx_radio, data)
                    if resp is not None:
                        if not isinstance(resp, str):
                            resp = str(resp)
                        if "Success" in resp:
                            status_dict = {
                                "status": "sent",
                                "bytes": len(data),
                                "response": resp,
                                "radio": tx_radio,
                                "syncword": LORA_SYNCWORD_TX,
                            }
                        else:
                            status_dict = {"status": "error", "error": resp}
                    else:
                        # Fallback to stream/raw transmission on the uplink radio
                        if self._state.device.send_radio_raw(tx_radio, data):
                            status_dict = {
                                "status": "sent",
                                "bytes": len(data),
                                "response": "Stream TX Success",
                                "radio": tx_radio,
                                "syncword": LORA_SYNCWORD_TX,
                            }
                        else:
                            status_dict = {
                                "status": "error",
                                "error": f"No radio available on Radio {tx_radio}",
                            }
                except Exception as e:
                    status_dict = {"status": "error", "error": str(e)}
                finally:
                    # Never let the revert mask a successful transmit, and never
                    # let a revert failure abort the calling command.
                    try:
                        self._restore_rx(tx_radio, prev_syncword)
                    except Exception:
                        pass
                    self._state.tx_in_progress = False

            return status_dict

        return {"status": "sent_simulated", "bytes": len(data), "data_hex": data.hex()}

    def send_tc(self, apid: int, payload: bytes) -> dict:
        """Build CCSDS TC frame and send."""
        frame = build_tc(apid, payload)
        result = self.send_raw(frame)
        result["frame_hex"] = frame.hex()
        return result
