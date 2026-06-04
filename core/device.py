"""FlatSat device driver — sync serial I/O for Flask.

Simplified from flatsatTUI/device.py: no asyncio, no command queue,
direct serial read/write with timeouts. One device at a time.
"""

import re
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
        """True only if radio0 and shell are open (radio1 is optional for GS-only boards)."""
        return all(s is not None and s.is_open for s in [self._radio0, self._shell])

    def connect(self) -> dict[str, bool]:
        """Open all serial ports. Returns {endpoint: success}.

        On partial failure, closes any ports that were successfully opened.
        """
        result = {}
        for name, port_path, attr in [
            ("radio0", self._discovered.radio0_port, "_radio0"),
            ("radio1", self._discovered.radio1_port, "_radio1"),
            ("shell", self._discovered.shell_port, "_shell"),
        ]:
            if port_path:
                try:
                    ser = serial.Serial(
                        port_path,
                        BAUDRATE,
                        timeout=1.0,
                        write_timeout=1.0,
                        dsrdtr=False,
                        rtscts=False,
                    )
                    setattr(self, attr, ser)
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

        return result

    def _drain_boot_banner(self):
        """Drain firmware boot text from shell before sending real commands.

        After USB CDC open, the firmware may still be printing its boot banner.
        We wait for the boot output to settle, drain it, then send a no-op
        command to confirm the shell is responsive before returning.
        """
        import time

        with self._shell_lock:
            try:
                # Wait for firmware boot to complete
                time.sleep(1.0)
                # Drain all boot text
                if self._shell.in_waiting:
                    self._shell.read(self._shell.in_waiting)
                self._shell.reset_input_buffer()
                # Send bare newline to sync shell parser
                self._shell.write(b"\r\n")
                self._shell.flush()
                time.sleep(0.3)
                # Drain the shell's response to the empty line
                if self._shell.in_waiting:
                    self._shell.read(self._shell.in_waiting)
                self._shell.reset_input_buffer()
            except Exception:
                pass

    def disconnect(self):
        """Close all serial ports, holding all locks to prevent races."""
        with self._radio0_lock, self._radio1_lock, self._shell_lock:
            for attr in ["_radio0", "_radio1", "_shell"]:
                ser = getattr(self, attr, None)
                if ser and ser.is_open:
                    try:
                        ser.close()
                    except Exception:
                        pass
                setattr(self, attr, None)

    def send_shell_command(self, cmd: str, timeout: float = 2.0) -> str | None:
        """Send command to Shell (CDC2), return first response line."""
        if not self._shell or not self._shell.is_open:
            return None
        with self._shell_lock:
            try:
                self._shell.timeout = timeout
                self._shell.reset_input_buffer()
                self._shell.write(f"{cmd}\r\n".encode("ascii"))
                self._shell.flush()
                response = self._shell.readline()
                if response:
                    return response.decode("ascii", errors="ignore").strip()
                return None
            except Exception:
                return None

    def send_shell_command_full(self, cmd: str, timeout: float = 2.0) -> str | None:
        """Send command to Shell (CDC2), return full multi-line response.

        Reads in a loop until no new data arrives for 100ms, up to timeout.
        """
        if not self._shell or not self._shell.is_open:
            return None
        with self._shell_lock:
            try:
                import time

                self._shell.timeout = 0.2
                self._shell.reset_input_buffer()
                self._shell.write(f"{cmd}\r\n".encode("ascii"))
                self._shell.flush()

                buf = b""
                deadline = time.time() + timeout
                while time.time() < deadline:
                    chunk = self._shell.read(self._shell.in_waiting or 1)
                    if chunk:
                        buf += chunk
                    elif buf:
                        break  # Had data, now nothing more — done
                    time.sleep(0.05)

                if buf:
                    return buf.decode("ascii", errors="ignore").strip()
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
