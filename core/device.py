"""FlatSat device driver — sync serial I/O for Flask.

Simplified from flatsatTUI/device.py: no asyncio, no command queue,
direct serial read/write with timeouts. One device at a time.
"""

import re

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

    @property
    def serial_number(self) -> str:
        return self._discovered.identity.serial_number

    @property
    def is_connected(self) -> bool:
        return any(s is not None and s.is_open for s in [self._radio0, self._radio1, self._shell])

    def connect(self) -> dict[str, bool]:
        """Open all serial ports. Returns {endpoint: success}."""
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
        return result

    def disconnect(self):
        """Close all serial ports."""
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

    def send_raw(self, data: bytes) -> bool:
        """Send raw bytes to Radio 0 (CDC0)."""
        if not self._radio0 or not self._radio0.is_open:
            return False
        try:
            self._radio0.write(data)
            self._radio0.flush()
            return True
        except Exception:
            return False

    def send_radio1_raw(self, data: bytes) -> bool:
        """Send raw bytes to Radio 1 (CDC1)."""
        if not self._radio1 or not self._radio1.is_open:
            return False
        try:
            self._radio1.write(data)
            self._radio1.flush()
            return True
        except Exception:
            return False

    def read_line(self, timeout: float = 1.0) -> str | None:
        """Read one line from Radio 0. Returns None on timeout."""
        if not self._radio0 or not self._radio0.is_open:
            return None
        try:
            self._radio0.timeout = timeout
            line = self._radio0.readline()
            if line:
                return line.decode("ascii", errors="ignore").strip()
            return None
        except Exception:
            return None
