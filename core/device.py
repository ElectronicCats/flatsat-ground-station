"""FlatSat device driver — sync serial I/O for Flask.

Simplified from flatsatTUI/device.py: no asyncio, no command queue,
direct serial read/write with timeouts. One device at a time.
"""

import os
import re
import sys
import threading

import serial

from core.constants import (
    BAUDRATE,
)
from core.serial_manager import DiscoveredDevice


def parse_lora_rx(line: str) -> dict | None:
    """Parse LoRa/FSK RX line into structured data.

    Formats:
        LoRa: "RX: <hex> | RSSI: <int> | SNR: <int>"
        FSK:  "FSK RX: <hex> | RSSI: <int> | Len: <int>"
    """
    lora_match = re.match(
        r"RX:\s*([A-Fa-f0-9]+)\s*\|\s*RSSI:\s*(-?\d+)\s*\|\s*SNR:\s*(-?\d+)",
        line,
    )
    if lora_match:
        return {
            "type": "lora_rx",
            "data": lora_match.group(1),
            "rssi": int(lora_match.group(2)),
            "snr": int(lora_match.group(3)),
        }

    fsk_match = re.match(
        r"FSK RX:\s*([A-Fa-f0-9]+)\s*\|\s*RSSI:\s*(-?\d+)\s*\|\s*Len:\s*(\d+)",
        line,
    )
    if fsk_match:
        return {
            "type": "fsk_rx",
            "data": fsk_match.group(1),
            "rssi": int(fsk_match.group(2)),
            "len": int(fsk_match.group(3)),
        }

    return None


class FlatSatDevice:
    """Sync serial interface to a single FlatSat (3 CDC endpoints)."""

    def __init__(self, discovered: DiscoveredDevice):
        self._discovered = discovered
        self._radio0: serial.Serial | None = None
        self._radio1: serial.Serial | None = None
        self._shell: serial.Serial | None = None
        self._shell_lock = threading.Lock()
        self._radio0_lock = threading.Lock()
        self._radio1_lock = threading.Lock()
        self.has_radio1 = True

    @property
    def serial_number(self) -> str:
        return self._discovered.identity.serial_number

    @property
    def is_connected(self) -> bool:
        """True only if radio0 and shell are open (radio1 is optional for GS-only boards) and physical ports exist."""
        is_mock = self._radio0 is not None and "Mock" in type(self._radio0).__name__
        for s, path in [(self._radio0, self._discovered.radio0_port), (self._shell, self._discovered.shell_port)]:
            if s is None or not s.is_open:
                return False
            if not is_mock and path:
                if path.startswith("/dev/"):
                    if not os.path.exists(path):
                        return False
                elif sys.platform == "win32":
                    import serial.tools.list_ports
                    active_ports = [p.device for p in serial.tools.list_ports.comports()]
                    if path not in active_ports:
                        return False
        return True

    def connect(self, forced_role: str | None = None) -> dict[str, bool]:
        """Open all serial ports. Returns {endpoint: success}.

        On partial failure, closes any ports that were successfully opened.

        ``forced_role`` controls whether connecting also changes the board's
        operating mode:

        - ``None`` (default): do NOT touch the mode. Connecting is pure I/O with
          no side effect on the board's role — it stays in whatever mode it was
          already in. The CLI relies on this so that querying/configuring a board
          never silently flips it to ground station. (Each CLI command is a
          separate process that connects and disconnects, so forcing a mode here
          would clobber the board's role on every single command.)
        - ``"satellite"`` / ``"gs"``: force the board into that mode after
          connecting. Used by the webapp, which owns one persistent connection
          and explicitly drives the board's role.
        """
        self.disconnect()

        # Gather targets
        targets = {"radio0": self._discovered.radio0_port, "shell": self._discovered.shell_port}
        if self.has_radio1:
            targets["radio1"] = self._discovered.radio1_port

        result = {}
        for name, path in targets.items():
            if path:
                try:
                    # In mock mode, we just pretend it succeeds
                    is_mock = os.environ.get("FLATSAT_MOCK") == "1"
                    if is_mock:
                        from unittest.mock import MagicMock
                        setattr(self, f"_{name}", MagicMock(is_open=True))
                        result[name] = True
                        continue

                    ser = serial.Serial(
                        path,
                        BAUDRATE,
                        timeout=1.0,
                        write_timeout=1.0,
                        dsrdtr=False,
                        rtscts=False,
                    )
                    # Explicitly assert DTR and RTS to enable virtual COM port CDC ACM communications.
                    try:
                        ser.dtr = True
                        ser.rts = True
                    except Exception:
                        pass
                    setattr(self, f"_{name}", ser)
                    result[name] = True
                except serial.SerialException:
                    result[name] = False
            else:
                result[name] = False

        # If mandatory ports failed, clean up the ones that opened
        if not result.get("radio0") or not result.get("shell"):
            self.disconnect()
        elif self._shell and self._shell.is_open:
            self._drain_boot_banner()
            # Force the device to the selected mode (sat or gs) if explicitly requested
            if forced_role in ("satellite", "gs"):
                cmd = "mode sat" if forced_role == "satellite" else "mode gs"
                for _attempt in range(3):
                    resp = self.send_shell_command_full(cmd, timeout=0.5)
                    if resp is not None:
                        break
                    import time
                    time.sleep(0.1)

        return result

    def _drain_boot_banner(self):
        """Drain firmware boot text from shell before sending real commands.

        The updated DUAL firmware defaults to GS mode at boot so no sat_telem
        interference; the 1 s USB settle delay in the firmware is the main wait.
        We allow 50 ms for USB CDC to settle, then drain whatever boot text
        arrived and sync the shell parser.
        """
        import time

        with self._shell_lock:
            try:
                # Wait for USB CDC setup and firmware init to settle (800ms)
                time.sleep(0.8)
                # Drain all boot text
                if self._shell.in_waiting:
                    self._shell.read(self._shell.in_waiting)
                self._shell.reset_input_buffer()
                # Send bare newline to sync shell parser
                self._shell.write(b"\r\n")
                self._shell.flush()
                time.sleep(0.05)
                # Drain the shell's response to the empty line
                if self._shell.in_waiting:
                    self._shell.read(self._shell.in_waiting)
                self._shell.reset_input_buffer()
            except Exception:
                pass

    def disconnect(self):
        """Close all serial ports, locking individually to prevent races and deadlocks."""
        for attr, lock in [("_radio0", self._radio0_lock), 
                           ("_radio1", self._radio1_lock), 
                           ("_shell", self._shell_lock)]:
            with lock:
                ser = getattr(self, attr, None)
                if ser and ser.is_open:
                    try:
                        ser.close()
                    except Exception:
                        pass
                setattr(self, attr, None)

    def send_shell_command(self, cmd: str, timeout: float = 2.0) -> str | None:
        """Send command to Shell (CDC2), return first response line."""
        resp = self.send_shell_command_full(cmd, timeout)
        if resp:
            lines = resp.splitlines()
            return lines[0] if lines else None
        return None

    def send_shell_command_full(self, cmd: str, timeout: float = 2.0) -> str | None:
        """Send command to Shell (CDC2), return full multi-line response.

        Uses the same algorithm as catnip's ShellConnection.send_command:
        - port timeout = 1.0 s  (blocking read, works with usbser.sys on Windows 11)
        - poll in_waiting every 20 ms to drain available bytes
        - exit when 150 ms of silence after last received byte (catnip _SILENCE_S)
        This avoids the in_waiting=0 bug when timeout=0 on Windows usbser.sys.
        """
        if not self._shell or not self._shell.is_open:
            return None
        with self._shell_lock:
            try:
                import time

                _SILENCE_S = 0.15  # 150 ms silence window — same as catnip

                self._shell.timeout = 1.0  # blocking read; usbser.sys needs non-zero
                self._shell.reset_input_buffer()
                self._shell.reset_output_buffer()
                self._shell.write(f"{cmd}\r\n".encode("ascii"))
                self._shell.flush()

                buf = b""
                deadline = time.monotonic() + timeout
                last_rx = None

                while time.monotonic() < deadline:
                    waiting = self._shell.in_waiting
                    if waiting:
                        buf += self._shell.read(waiting)
                        last_rx = time.monotonic()
                        time.sleep(0.02)
                    else:
                        if last_rx is not None and (time.monotonic() - last_rx) >= _SILENCE_S:
                            break
                        time.sleep(0.02)

                if buf:
                    decoded = buf.decode("ascii", errors="ignore").strip()
                    # Filter out background telemetry lines (RX: / FSK RX:)
                    filtered_lines = [
                        line for line in decoded.splitlines()
                        if not line.strip().startswith("RX:")
                        and not line.strip().startswith("FSK RX:")
                    ]
                    return "\n".join(filtered_lines).strip()
                return None
            except Exception:
                return None

    def send_raw(self, data: bytes) -> bool:
        """Send raw bytes to Radio 0 (CDC0)."""
        if not self._radio0 or not self._radio0.is_open:
            return False
        with self._radio0_lock:
            try:
                self._radio0.write(data)
                self._radio0.flush()
                return True
            except Exception:
                return False

    def send_radio0_raw(self, data: bytes) -> bool:
        """Send raw bytes to Radio 0 (CDC0 stream mode)."""
        if not self._radio0 or not self._radio0.is_open:
            return False
        with self._radio0_lock:
            try:
                self._radio0.write(data)
                self._radio0.flush()
                return True
            except Exception:
                return False

    def send_radio1_tx(self, data: bytes) -> str | None:
        """Send data via Radio 1 using TX command (LoRa command mode)."""
        if not self._radio1 or not self._radio1.is_open:
            return None
        with self._radio1_lock:
            try:
                self._radio1.timeout = 3.0
                self._radio1.reset_input_buffer()
                self._radio1.write(f"TX {data.hex()}\r\n".encode("ascii"))
                self._radio1.flush()
                response = self._radio1.readline()
                if response:
                    return response.decode("ascii", errors="ignore").strip()
                return None
            except Exception:
                return None

    def send_radio1_raw(self, data: bytes) -> bool:
        """Send raw bytes to Radio 1 (CDC1)."""
        if not self._radio1 or not self._radio1.is_open:
            return False
        with self._radio1_lock:
            try:
                self._radio1.write(data)
                self._radio1.flush()
                return True
            except Exception:
                return False

    def read_line(self, timeout: float = 1.0) -> str | None:
        """Read one line from Radio 0. Returns None on timeout."""
        return self.read_line_from_radio(0, timeout)

    def read_line_from_radio(self, radio_idx: int, timeout: float = 1.0) -> str | None:
        """Read one line from Radio 0 or Radio 1 depending on radio_idx."""
        radio = self._radio1 if radio_idx == 1 else self._radio0
        lock = self._radio1_lock if radio_idx == 1 else self._radio0_lock
        if not radio or not radio.is_open:
            return None
        with lock:
            try:
                radio.timeout = timeout
                line = radio.readline()
                if line:
                    return line.decode("ascii", errors="ignore").strip()
                return None
            except (serial.SerialException, OSError):
                return None
            except Exception:
                return None

    def send_radio_tx(self, radio_idx: int, data: bytes) -> str | None:
        """Send data via selected Radio using TX command (LoRa command mode)."""
        radio = self._radio1 if radio_idx == 1 else self._radio0
        lock = self._radio1_lock if radio_idx == 1 else self._radio0_lock
        if not radio or not radio.is_open:
            return None
        with lock:
            try:
                import time
                radio.timeout = 3.0
                
                # Send a newline to clear/terminate any garbage command in progress on the board
                radio.write(b"\r\n")
                radio.flush()
                time.sleep(0.1)
                
                # Drain the response to the empty command/newline
                if radio.in_waiting:
                    radio.read(radio.in_waiting)
                
                # Send the real command
                radio.reset_input_buffer()
                radio.write(f"TX {data.hex()}\r\n".encode("ascii"))
                radio.flush()
                response = radio.readline()
                if response:
                    return response.decode("ascii", errors="ignore").strip()
                return None
            except Exception:
                return None

    def send_radio_raw(self, radio_idx: int, data: bytes) -> bool:
        """Send raw bytes to selected Radio."""
        radio = self._radio1 if radio_idx == 1 else self._radio0
        lock = self._radio1_lock if radio_idx == 1 else self._radio0_lock
        if not radio or not radio.is_open:
            return False
        with lock:
            try:
                radio.write(data)
                radio.flush()
                return True
            except Exception:
                return False

    def reset_radio_input_buffers(self):
        """Reset/drain input buffer for both radio ports to drop old messages."""
        for ser, lock in [(self._radio0, self._radio0_lock), (self._radio1, self._radio1_lock)]:
            if ser and ser.is_open:
                with lock:
                    try:
                        ser.reset_input_buffer()
                    except Exception:
                        pass
