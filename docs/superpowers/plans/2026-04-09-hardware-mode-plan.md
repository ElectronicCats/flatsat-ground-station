# Hardware Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add USB serial connectivity so the webapp can communicate with a real FlatSat instead of generating mock telemetry.

**Architecture:** `core/serial_manager.py` discovers FlatSats by VID/PID and groups 3 CDC endpoints per device. `core/device.py` provides sync serial I/O. The webapp exposes scan/connect/disconnect API routes and switches its telemetry background thread between mock and hardware modes.

**Tech Stack:** PySerial 3.5, existing Flask + Flask-SocketIO

**Spec:** `docs/superpowers/specs/2026-04-09-hardware-mode-design.md`

**TUI reference:** `/home/sabas/Documents/electroniccats/flat-sat-fw-interno/flatsatTUI/discovery.py` and `device.py`

---

## File Structure

```
core/
├── serial_manager.py   # NEW: device discovery (adapted from TUI discovery.py)
├── device.py           # NEW: sync serial I/O (adapted from TUI device.py)
├── __init__.py         # MODIFY: add new exports

webapp/
├── app.py              # MODIFY: add hardware routes, update telemetry thread
├── radio_bridge.py     # MODIFY: use real device when connected
├── templates/
│   └── dashboard.html  # MODIFY: add hardware status bar

tests/
├── test_serial_manager.py  # NEW
├── test_device.py          # NEW
├── test_hardware_api.py    # NEW
```

---

### Task 1: Core serial manager

**Files:**
- Create: `core/serial_manager.py`
- Create: `tests/test_serial_manager.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_serial_manager.py`:
```python
from unittest.mock import MagicMock, patch

from core.serial_manager import (
    DeviceIdentity,
    DiscoveredDevice,
    discover_devices,
    _extract_serial_number,
    _group_ports_by_device,
    _map_endpoints_intelligent,
)
from core.constants import (
    ENDPOINT_RADIO0,
    ENDPOINT_RADIO1,
    ENDPOINT_SHELL,
    DeviceHealth,
)


def test_extract_serial_number():
    assert _extract_serial_number("USB VID:PID=1209:BABC SER=503342353230000E") == "503342353230000E"


def test_extract_serial_number_none():
    assert _extract_serial_number("") is None
    assert _extract_serial_number("no serial here") is None


def test_device_identity_equality():
    a = DeviceIdentity("ABC123")
    b = DeviceIdentity("ABC123")
    c = DeviceIdentity("DEF456")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)


def test_discovered_device_complete():
    dev = DiscoveredDevice(
        identity=DeviceIdentity("ABC"),
        ports={
            ENDPOINT_RADIO0: "/dev/ttyACM0",
            ENDPOINT_RADIO1: "/dev/ttyACM1",
            ENDPOINT_SHELL: "/dev/ttyACM2",
        },
    )
    assert dev.is_complete
    assert dev.health == DeviceHealth.HEALTHY
    assert dev.radio0_port == "/dev/ttyACM0"
    assert dev.radio1_port == "/dev/ttyACM1"
    assert dev.shell_port == "/dev/ttyACM2"


def test_discovered_device_partial():
    dev = DiscoveredDevice(
        identity=DeviceIdentity("ABC"),
        ports={ENDPOINT_SHELL: "/dev/ttyACM2"},
    )
    assert not dev.is_complete
    assert dev.health == DeviceHealth.PARTIAL
    assert dev.radio0_port is None


def test_map_endpoints_by_description():
    ports = [
        MagicMock(device="/dev/ttyACM0", description="Flat-Sat - Cat-Radio0"),
        MagicMock(device="/dev/ttyACM1", description="Flat-Sat - Cat-Radio1"),
        MagicMock(device="/dev/ttyACM2", description="Flat-Sat - Cat-Shell"),
    ]
    result = _map_endpoints_intelligent(ports)
    assert result[ENDPOINT_RADIO0] == "/dev/ttyACM0"
    assert result[ENDPOINT_RADIO1] == "/dev/ttyACM1"
    assert result[ENDPOINT_SHELL] == "/dev/ttyACM2"


def test_map_endpoints_positional_fallback():
    ports = [
        MagicMock(device="/dev/ttyACM0", description="Unknown CDC"),
        MagicMock(device="/dev/ttyACM1", description="Unknown CDC"),
        MagicMock(device="/dev/ttyACM2", description="Unknown CDC"),
    ]
    result = _map_endpoints_intelligent(ports)
    assert result[ENDPOINT_RADIO0] == "/dev/ttyACM0"
    assert result[ENDPOINT_RADIO1] == "/dev/ttyACM1"
    assert result[ENDPOINT_SHELL] == "/dev/ttyACM2"


def test_group_ports_by_device():
    p1 = MagicMock(hwid="SER=AAAA", device="/dev/ttyACM0", location=None)
    p2 = MagicMock(hwid="SER=AAAA", device="/dev/ttyACM1", location=None)
    p3 = MagicMock(hwid="SER=BBBB", device="/dev/ttyACM2", location=None)
    groups = _group_ports_by_device([p1, p2, p3])
    assert len(groups) == 2
    assert len(groups["AAAA"]) == 2
    assert len(groups["BBBB"]) == 1


@patch("core.serial_manager.serial.tools.list_ports.comports")
def test_discover_devices_empty(mock_comports):
    mock_comports.return_value = []
    assert discover_devices() == []


@patch("core.serial_manager.serial.tools.list_ports.comports")
def test_discover_devices_finds_flatsat(mock_comports):
    ports = []
    for i, desc in enumerate(["Cat-Radio0", "Cat-Radio1", "Cat-Shell"]):
        p = MagicMock()
        p.vid = 0x1209
        p.pid = 0xBABC
        p.device = f"/dev/ttyACM{i}"
        p.description = f"Flat-Sat - {desc}"
        p.hwid = "SER=TESTSERIAL"
        p.location = None
        ports.append(p)
    mock_comports.return_value = ports

    devices = discover_devices()
    assert len(devices) == 1
    assert devices[0].is_complete
    assert devices[0].identity.serial_number == "TESTSERIAL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_serial_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/serial_manager.py`:
```python
"""USB serial device discovery for FlatSat ground station.

Discovers FlatSat devices by VID/PID (0x1209:0xBABC), groups 3 CDC
endpoints per device by serial number, and maps them to Radio0/Radio1/Shell.
Adapted from flatsatTUI/discovery.py.
"""

import re
from dataclasses import dataclass, field

import serial.tools.list_ports

from core.constants import (
    USB_VID,
    USB_PID,
    ENDPOINT_RADIO0,
    ENDPOINT_RADIO1,
    ENDPOINT_SHELL,
    DeviceHealth,
)


@dataclass(frozen=True)
class DeviceIdentity:
    """Stable identity for a physical FlatSat device."""

    serial_number: str
    usb_bus: int | None = None
    usb_address: int | None = None

    def __hash__(self):
        return hash(self.serial_number)

    def __eq__(self, other):
        if not isinstance(other, DeviceIdentity):
            return False
        return self.serial_number == other.serial_number

    def __str__(self):
        return f"FlatSat:{self.serial_number[:8]}"


@dataclass
class DiscoveredDevice:
    """A discovered FlatSat with its endpoints."""

    identity: DeviceIdentity
    ports: dict[str, str] = field(default_factory=dict)

    @property
    def radio0_port(self) -> str | None:
        return self.ports.get(ENDPOINT_RADIO0)

    @property
    def radio1_port(self) -> str | None:
        return self.ports.get(ENDPOINT_RADIO1)

    @property
    def shell_port(self) -> str | None:
        return self.ports.get(ENDPOINT_SHELL)

    @property
    def health(self) -> DeviceHealth:
        if self.radio0_port and self.radio1_port and self.shell_port:
            return DeviceHealth.HEALTHY
        elif self.shell_port:
            return DeviceHealth.PARTIAL
        else:
            return DeviceHealth.CRITICAL

    @property
    def is_complete(self) -> bool:
        return all([self.radio0_port, self.radio1_port, self.shell_port])


def _extract_serial_number(hwid: str) -> str | None:
    """Extract serial number from hwid string (SER=XXXX pattern)."""
    if not hwid:
        return None
    match = re.search(r"SER=([A-Fa-f0-9]+)", hwid)
    return match.group(1) if match else None


def _group_ports_by_device(ports: list) -> dict[str, list]:
    """Group ports by device serial number."""
    groups: dict[str, list] = {}
    for port in ports:
        serial_num = _extract_serial_number(port.hwid) if port.hwid else None
        if not serial_num and hasattr(port, "location") and port.location:
            serial_num = f"loc-{port.location}"
        if not serial_num:
            serial_num = f"unknown-{port.device}"
        groups.setdefault(serial_num, []).append(port)
    return groups


def _map_endpoints_intelligent(ports: list) -> dict[str, str]:
    """Map ports to endpoint names by description, with positional fallback."""
    ports_dict: dict[str, str] = {}
    sorted_ports = sorted(ports, key=lambda p: p.device)

    # Strategy 1: match by description string
    for port in sorted_ports:
        desc = (port.description or "").lower()
        if "shell" in desc:
            ports_dict[ENDPOINT_SHELL] = port.device
        elif "radio0" in desc or "radio 0" in desc:
            ports_dict[ENDPOINT_RADIO0] = port.device
        elif "radio1" in desc or "radio 1" in desc:
            ports_dict[ENDPOINT_RADIO1] = port.device

    # Strategy 2: positional fallback
    if len(ports_dict) < 3:
        fallback = {0: ENDPOINT_RADIO0, 1: ENDPOINT_RADIO1, 2: ENDPOINT_SHELL}
        for i, port in enumerate(sorted_ports[:3]):
            name = fallback.get(i)
            if name and name not in ports_dict:
                ports_dict[name] = port.device

    return ports_dict


def discover_devices() -> list[DiscoveredDevice]:
    """Discover all connected FlatSat devices by VID/PID."""
    all_ports = list(serial.tools.list_ports.comports())
    cat_ports = [p for p in all_ports if p.vid == USB_VID and p.pid == USB_PID]
    if not cat_ports:
        return []

    cat_ports.sort(key=lambda p: p.device)
    groups = _group_ports_by_device(cat_ports)
    devices = []

    for serial_num, ports in groups.items():
        ports.sort(key=lambda p: p.device)
        identity = DeviceIdentity(serial_number=serial_num)
        endpoint_map = _map_endpoints_intelligent(ports)
        devices.append(DiscoveredDevice(identity=identity, ports=endpoint_map))

    return devices
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_serial_manager.py -v`
Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/serial_manager.py tests/test_serial_manager.py
git commit -m "feat(core): add serial manager for FlatSat USB discovery"
```

---

### Task 2: Core device driver (sync)

**Files:**
- Create: `core/device.py`
- Create: `tests/test_device.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_device.py`:
```python
import re
from unittest.mock import MagicMock, patch, PropertyMock

from core.device import FlatSatDevice, parse_lora_rx
from core.serial_manager import DiscoveredDevice, DeviceIdentity
from core.constants import ENDPOINT_RADIO0, ENDPOINT_RADIO1, ENDPOINT_SHELL


def _make_discovered(
    serial="TEST123",
    r0="/dev/ttyACM0",
    r1="/dev/ttyACM1",
    sh="/dev/ttyACM2",
):
    return DiscoveredDevice(
        identity=DeviceIdentity(serial),
        ports={
            ENDPOINT_RADIO0: r0,
            ENDPOINT_RADIO1: r1,
            ENDPOINT_SHELL: sh,
        },
    )


def test_parse_lora_rx_valid():
    line = "RX: 08010001DEADBEEF | RSSI: -45 | SNR: 8"
    result = parse_lora_rx(line)
    assert result is not None
    assert result["data"] == "08010001DEADBEEF"
    assert result["rssi"] == -45
    assert result["snr"] == 8


def test_parse_lora_rx_invalid():
    assert parse_lora_rx("some random text") is None
    assert parse_lora_rx("") is None


def test_parse_fsk_rx():
    line = "FSK RX: AABBCC | RSSI: -60 | Len: 3"
    result = parse_lora_rx(line)
    assert result is not None
    assert result["data"] == "AABBCC"
    assert result["rssi"] == -60


def test_flatsat_device_init():
    disc = _make_discovered()
    dev = FlatSatDevice(disc)
    assert dev.serial_number == "TEST123"
    assert not dev.is_connected


@patch("core.device.serial.Serial")
def test_flatsat_device_connect(mock_serial_cls):
    mock_ser = MagicMock()
    mock_serial_cls.return_value = mock_ser
    disc = _make_discovered()
    dev = FlatSatDevice(disc)

    result = dev.connect()
    assert result["radio0"] is True
    assert result["radio1"] is True
    assert result["shell"] is True
    assert dev.is_connected


@patch("core.device.serial.Serial")
def test_flatsat_device_disconnect(mock_serial_cls):
    mock_ser = MagicMock()
    mock_serial_cls.return_value = mock_ser
    disc = _make_discovered()
    dev = FlatSatDevice(disc)
    dev.connect()
    dev.disconnect()
    assert not dev.is_connected
    assert mock_ser.close.call_count == 3


@patch("core.device.serial.Serial")
def test_send_shell_command(mock_serial_cls):
    mock_ser = MagicMock()
    mock_ser.readline.return_value = b"OK\r\n"
    mock_serial_cls.return_value = mock_ser
    disc = _make_discovered()
    dev = FlatSatDevice(disc)
    dev.connect()

    resp = dev.send_shell_command("status")
    assert resp == "OK"
    mock_ser.write.assert_called_with(b"status\r\n")


@patch("core.device.serial.Serial")
def test_send_raw(mock_serial_cls):
    mock_ser = MagicMock()
    mock_serial_cls.return_value = mock_ser
    disc = _make_discovered()
    dev = FlatSatDevice(disc)
    dev.connect()

    assert dev.send_raw(b"\x08\x01") is True
    mock_ser.write.assert_called_with(b"\x08\x01")


@patch("core.device.serial.Serial")
def test_read_line(mock_serial_cls):
    mock_ser = MagicMock()
    mock_ser.readline.return_value = b"RX: AABB | RSSI: -50 | SNR: 5\r\n"
    mock_serial_cls.return_value = mock_ser
    disc = _make_discovered()
    dev = FlatSatDevice(disc)
    dev.connect()

    line = dev.read_line()
    assert line == "RX: AABB | RSSI: -50 | SNR: 5"


@patch("core.device.serial.Serial")
def test_read_line_timeout(mock_serial_cls):
    mock_ser = MagicMock()
    mock_ser.readline.return_value = b""
    mock_serial_cls.return_value = mock_ser
    disc = _make_discovered()
    dev = FlatSatDevice(disc)
    dev.connect()

    assert dev.read_line() is None


@patch("core.device.serial.Serial")
def test_send_not_connected(mock_serial_cls):
    disc = _make_discovered()
    dev = FlatSatDevice(disc)
    assert dev.send_shell_command("status") is None
    assert dev.send_raw(b"\x00") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_device.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

`core/device.py`:
```python
"""FlatSat device driver — sync serial I/O for Flask.

Simplified from flatsatTUI/device.py: no asyncio, no command queue,
direct serial read/write with timeouts. One device at a time.
"""

import re

import serial

from core.constants import (
    BAUDRATE,
    ENDPOINT_RADIO0,
    ENDPOINT_RADIO1,
    ENDPOINT_SHELL,
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
        return any(
            s is not None and s.is_open
            for s in [self._radio0, self._radio1, self._shell]
        )

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_device.py -v`
Expected: all 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/device.py tests/test_device.py
git commit -m "feat(core): add sync FlatSat device driver"
```

---

### Task 3: Update core exports

**Files:**
- Modify: `core/__init__.py`

- [ ] **Step 1: Add new exports**

Add these imports to `core/__init__.py`:

```python
from core.device import FlatSatDevice, parse_lora_rx
from core.serial_manager import DeviceIdentity, DiscoveredDevice, discover_devices
```

- [ ] **Step 2: Verify all tests pass**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add core/__init__.py
git commit -m "feat(core): export serial manager and device driver"
```

---

### Task 4: Hardware API routes and webapp integration

**Files:**
- Modify: `webapp/app.py`
- Modify: `webapp/radio_bridge.py`
- Modify: `webapp/templates/dashboard.html`
- Create: `tests/test_hardware_api.py`

This is the largest task — it wires everything together.

- [ ] **Step 1: Write the failing tests**

`tests/test_hardware_api.py`:
```python
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from webapp.config import TestConfig
from webapp.db import init_db
from webapp.seed import seed_db


@pytest.fixture
def app():
    from webapp.app import create_app

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app(TestConfig, db_path=db_path)
    with app.app_context():
        init_db()
        seed_db()
        yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def auth_client(app):
    client = app.test_client()
    client.post("/login", data={"username": "operator", "password": "operator123"})
    return client


def test_hardware_status_simulated(auth_client):
    resp = auth_client.get("/api/hardware/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "simulated"


@patch("webapp.app.discover_devices")
def test_hardware_scan(mock_discover, auth_client):
    mock_dev = MagicMock()
    mock_dev.identity.serial_number = "TESTSERIAL"
    mock_dev.is_complete = True
    mock_dev.radio0_port = "/dev/ttyACM0"
    mock_dev.radio1_port = "/dev/ttyACM1"
    mock_dev.shell_port = "/dev/ttyACM2"
    mock_dev.health.name = "HEALTHY"
    mock_discover.return_value = [mock_dev]

    resp = auth_client.post("/api/hardware/scan")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["serial_number"] == "TESTSERIAL"


def test_hardware_connect_no_device(auth_client):
    resp = auth_client.post(
        "/api/hardware/connect",
        json={"serial_number": "NONEXISTENT"},
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_hardware_disconnect_when_simulated(auth_client):
    resp = auth_client.post("/api/hardware/disconnect")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "simulated"


@patch("webapp.app.discover_devices")
@patch("webapp.app.FlatSatDevice")
def test_hardware_connect_success(mock_device_cls, mock_discover, auth_client):
    mock_discovered = MagicMock()
    mock_discovered.identity.serial_number = "ABC123"
    mock_discovered.is_complete = True
    mock_discovered.radio0_port = "/dev/ttyACM0"
    mock_discovered.radio1_port = "/dev/ttyACM1"
    mock_discovered.shell_port = "/dev/ttyACM2"
    mock_discovered.health.name = "HEALTHY"
    mock_discover.return_value = [mock_discovered]

    mock_dev = MagicMock()
    mock_dev.connect.return_value = {"radio0": True, "radio1": True, "shell": True}
    mock_dev.is_connected = True
    mock_dev.serial_number = "ABC123"
    mock_device_cls.return_value = mock_dev

    # First scan
    auth_client.post("/api/hardware/scan")

    # Then connect
    resp = auth_client.post(
        "/api/hardware/connect",
        json={"serial_number": "ABC123"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "hardware"

    # Status should now be hardware
    resp = auth_client.get("/api/hardware/status")
    assert resp.get_json()["mode"] == "hardware"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hardware_api.py -v`
Expected: FAIL (routes not found)

- [ ] **Step 3: Update webapp/radio_bridge.py**

Replace `webapp/radio_bridge.py` with:

```python
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
        return not self._state.is_simulated

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
```

- [ ] **Step 4: Update webapp/app.py — add hardware routes and state management**

Read the current `webapp/app.py`, then add the following changes:

At the top, add imports:
```python
from core.serial_manager import discover_devices
from core.device import FlatSatDevice
from core.state import GroundStationState
```

Inside `create_app()`, after `socketio.init_app(app, cors_allowed_origins="*")`, add:
```python
    # Shared ground station state
    gs_state = GroundStationState()
    app.config["GS_STATE"] = gs_state
    app.config["SCANNED_DEVICES"] = {}  # serial_number -> DiscoveredDevice
```

Update the existing `/api/radio/send` route to use `gs_state`:
```python
    @app.route("/api/radio/send", methods=["POST"])
    @login_required
    def api_radio_send():
        from webapp.radio_bridge import RadioBridge

        data = request.get_json(silent=True) or {}
        raw_hex = data.get("data", "")
        try:
            raw_bytes = bytes.fromhex(raw_hex)
        except ValueError:
            return {"error": "Invalid hex data"}, 400
        bridge = RadioBridge(app.config["GS_STATE"])
        return bridge.send_raw(raw_bytes)
```

Add the four hardware routes inside `create_app()`:
```python
    @app.route("/api/hardware/status")
    @login_required
    def api_hardware_status():
        gs = app.config["GS_STATE"]
        if gs.is_simulated:
            return {"mode": "simulated"}
        return {
            "mode": "hardware",
            "serial_number": gs.device.serial_number if gs.device else None,
        }

    @app.route("/api/hardware/scan", methods=["POST"])
    @login_required
    def api_hardware_scan():
        devices = discover_devices()
        scanned = {}
        result = []
        for d in devices:
            sn = d.identity.serial_number
            scanned[sn] = d
            result.append({
                "serial_number": sn,
                "is_complete": d.is_complete,
                "health": d.health.name,
                "radio0": d.radio0_port,
                "radio1": d.radio1_port,
                "shell": d.shell_port,
            })
        app.config["SCANNED_DEVICES"] = scanned
        return {"devices": result}

    @app.route("/api/hardware/connect", methods=["POST"])
    @login_required
    def api_hardware_connect():
        data = request.get_json(silent=True) or {}
        serial_number = data.get("serial_number", "")

        # Find in scanned devices
        scanned = app.config.get("SCANNED_DEVICES", {})
        discovered = scanned.get(serial_number)
        if not discovered:
            return {"error": f"Device {serial_number} not found. Run scan first."}, 404

        # Disconnect current device if any
        gs = app.config["GS_STATE"]
        if gs.device:
            gs.device.disconnect()

        # Connect new device
        device = FlatSatDevice(discovered)
        connect_result = device.connect()

        if device.is_connected:
            gs.set_hardware(device)
            return {
                "mode": "hardware",
                "serial_number": serial_number,
                "endpoints": connect_result,
            }
        return {"error": "Failed to connect", "endpoints": connect_result}, 500

    @app.route("/api/hardware/disconnect", methods=["POST"])
    @login_required
    def api_hardware_disconnect():
        gs = app.config["GS_STATE"]
        if gs.device:
            gs.device.disconnect()
        gs.set_simulated()
        return {"mode": "simulated"}
```

Update `start_mock_telemetry` to handle both modes:
```python
def start_mock_telemetry(app):
    """Background thread: emit telemetry (mock or hardware)."""
    from core.telemetry import generate_mock_telemetry, decode_tm_payload
    from core.ccsds import parse_frame
    from core.device import parse_lora_rx
    from datetime import datetime

    def _loop():
        while True:
            gs = app.config.get("GS_STATE")

            if gs and not gs.is_simulated and gs.device:
                # HARDWARE MODE: read from Radio 0
                try:
                    line = gs.device.read_line(timeout=1.0)
                    if line:
                        parsed = parse_lora_rx(line)
                        if parsed:
                            raw_bytes = bytes.fromhex(parsed["data"])
                            pkt = parse_frame(raw_bytes)
                            if pkt:
                                decoded = decode_tm_payload(pkt.apid, pkt.payload)
                                with app.app_context():
                                    from webapp.db import get_db
                                    db = get_db()
                                    db.execute(
                                        "INSERT INTO telemetry "
                                        "(timestamp, apid, spacecraft_id, temperature, pressure, humidity, "
                                        "accel_x, accel_y, accel_z, raw_hex) "
                                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (
                                            datetime.now().isoformat(),
                                            pkt.apid,
                                            2,
                                            decoded.get("temperature"),
                                            decoded.get("pressure"),
                                            decoded.get("humidity"),
                                            decoded.get("accel_x"),
                                            decoded.get("accel_y"),
                                            decoded.get("accel_z"),
                                            parsed["data"],
                                        ),
                                    )
                                    db.commit()
                                socketio.emit("telemetry_update", {
                                    "apid": pkt.apid,
                                    "raw_hex": parsed["data"],
                                    "decoded": decoded,
                                    "timestamp": pkt.timestamp,
                                    "rssi": parsed.get("rssi"),
                                    "snr": parsed.get("snr"),
                                })
                            continue
                except Exception:
                    pass
                time.sleep(0.1)
            else:
                # SIMULATED MODE: generate mock
                with app.app_context():
                    tm = generate_mock_telemetry()
                    socketio.emit("telemetry_update", {
                        "apid": tm["apid"],
                        "raw_hex": tm["raw_hex"],
                        "decoded": tm["decoded"],
                        "timestamp": tm["timestamp"],
                    })
                time.sleep(2)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
```

- [ ] **Step 5: Update dashboard.html — add hardware status bar**

Replace the content block in `webapp/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block head %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
{% endblock %}
{% block content %}
<h1>Mission Dashboard</h1>

<div id="hw-status" style="padding:10px; margin-bottom:15px; border:1px solid #333; background:#111;">
    <span id="hw-mode" style="font-weight:bold;">SIMULATED</span>
    <span id="hw-serial"></span>
    <span id="hw-rssi"></span>
    <button onclick="hwScan()" style="margin-left:15px;">Scan</button>
    <button onclick="hwConnect()" style="margin-left:5px;" id="btn-connect" disabled>Connect</button>
    <button onclick="hwDisconnect()" style="margin-left:5px;">Disconnect</button>
    <select id="hw-devices" style="margin-left:10px; display:none;"></select>
</div>

<p>Spacecraft ID: 0x02 | User: {{ g.username }} ({{ g.role }})</p>

<h2>Live Telemetry</h2>
<div id="telemetry-status">Connecting...</div>
<table id="telemetry-table">
    <thead>
        <tr>
            <th>Timestamp</th><th>APID</th><th>Temperature</th>
            <th>Pressure</th><th>Humidity</th>
            <th>Accel X</th><th>Accel Y</th><th>Accel Z</th>
            <th>RSSI</th><th>SNR</th>
        </tr>
    </thead>
    <tbody id="telemetry-body"></tbody>
</table>

<script>
async function hwStatus() {
    const resp = await fetch("/api/hardware/status");
    const data = await resp.json();
    const el = document.getElementById("hw-mode");
    if (data.mode === "hardware") {
        el.textContent = "HARDWARE";
        el.style.color = "#00ff41";
        document.getElementById("hw-serial").textContent = " | SN: " + data.serial_number;
    } else {
        el.textContent = "SIMULATED";
        el.style.color = "#ffaa00";
        document.getElementById("hw-serial").textContent = "";
    }
}

async function hwScan() {
    const resp = await fetch("/api/hardware/scan", {method: "POST"});
    const data = await resp.json();
    const sel = document.getElementById("hw-devices");
    sel.innerHTML = "";
    sel.style.display = data.devices.length > 0 ? "inline" : "none";
    document.getElementById("btn-connect").disabled = data.devices.length === 0;
    data.devices.forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.serial_number;
        opt.textContent = d.serial_number.substring(0, 8) + " (" + d.health + ")";
        sel.appendChild(opt);
    });
}

async function hwConnect() {
    const sn = document.getElementById("hw-devices").value;
    if (!sn) return;
    await fetch("/api/hardware/connect", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({serial_number: sn})
    });
    hwStatus();
}

async function hwDisconnect() {
    await fetch("/api/hardware/disconnect", {method: "POST"});
    hwStatus();
    document.getElementById("hw-devices").style.display = "none";
    document.getElementById("btn-connect").disabled = true;
}

hwStatus();
</script>

<script src="/static/js/telemetry.js"></script>
{% endblock %}
```

- [ ] **Step 6: Update telemetry.js to show RSSI/SNR**

Replace `webapp/static/js/telemetry.js`:

```javascript
const socket = io();
const MAX_ROWS = 50;

socket.on("connect", function() {
    document.getElementById("telemetry-status").textContent = "Connected";
});

socket.on("disconnect", function() {
    document.getElementById("telemetry-status").textContent = "Disconnected";
});

socket.on("telemetry_update", function(data) {
    const tbody = document.getElementById("telemetry-body");
    const row = document.createElement("tr");
    const d = data.decoded || {};

    row.innerHTML = [
        new Date(data.timestamp * 1000).toISOString(),
        "0x" + data.apid.toString(16).padStart(3, "0"),
        d.temperature !== undefined ? d.temperature.toFixed(2) + " C" : "-",
        d.pressure !== undefined ? d.pressure.toFixed(1) + " hPa" : "-",
        d.humidity !== undefined ? d.humidity + "%" : "-",
        d.accel_x !== undefined ? d.accel_x : "-",
        d.accel_y !== undefined ? d.accel_y : "-",
        d.accel_z !== undefined ? d.accel_z : "-",
        data.rssi !== undefined ? data.rssi + " dBm" : "-",
        data.snr !== undefined ? data.snr + " dB" : "-",
    ].map(v => "<td>" + v + "</td>").join("");

    tbody.insertBefore(row, tbody.firstChild);

    // Update RSSI display in status bar
    if (data.rssi !== undefined) {
        const el = document.getElementById("hw-rssi");
        if (el) el.textContent = " | RSSI: " + data.rssi + " dBm | SNR: " + data.snr + " dB";
    }

    while (tbody.children.length > MAX_ROWS) {
        tbody.removeChild(tbody.lastChild);
    }
});
```

- [ ] **Step 7: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add webapp/app.py webapp/radio_bridge.py webapp/templates/dashboard.html webapp/static/js/telemetry.js tests/test_hardware_api.py
git commit -m "feat(webapp): add hardware connect/disconnect with USB serial support"
```

---

## Summary

| Task | Component | Files |
|------|-----------|-------|
| 1 | Serial manager (discovery) | core/serial_manager.py, tests/test_serial_manager.py |
| 2 | Device driver (sync) | core/device.py, tests/test_device.py |
| 3 | Core exports | core/__init__.py |
| 4 | Hardware API + webapp integration | webapp/app.py, radio_bridge.py, dashboard.html, telemetry.js, tests/test_hardware_api.py |
