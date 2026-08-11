"""USB serial device discovery for FlatSat ground station.

Discovers FlatSat devices by VID/PID (0x1209:0xBABC), groups 3 CDC
endpoints per device by serial number, and maps them to Radio0/Radio1/Shell.

Port-mapping logic mirrors catnip (CatSniffer-Tools/catnip/modules/core/usb_connection.py)
which is the reference implementation that works reliably on Windows 11.

Cross-platform notes:
    Linux   — location field always present; description may contain role name.
    macOS   — location field present; description may be generic.
    Windows — location may be absent for some interfaces; MI_ in HWID is used.
              Strategies 1 and 2 are preferred; positional fallback is last resort.
"""

import re
import sys
from dataclasses import dataclass, field

import serial.tools.list_ports

from core.constants import (
    ENDPOINT_RADIO0,
    ENDPOINT_RADIO1,
    ENDPOINT_SHELL,
    USB_PID,
    USB_VID,
    DeviceHealth,
)

# ── USB interface index → endpoint role ─────────────────────────────────────
# Each CDC-ACM instance occupies 2 USB interfaces (data + control), so the
# communication interface numbers are 0, 2, 4 — matching catnip's _INTF_TO_ROLE.
_INTF_TO_ENDPOINT = {0: ENDPOINT_RADIO0, 2: ENDPOINT_RADIO1, 4: ENDPOINT_SHELL}

# ── Description keyword → endpoint role ─────────────────────────────────────
_DESC_TO_ENDPOINT = {
    "shell":   ENDPOINT_SHELL,
    "radio0":  ENDPOINT_RADIO0,
    "radio 0": ENDPOINT_RADIO0,
    "radio1":  ENDPOINT_RADIO1,
    "radio 1": ENDPOINT_RADIO1,
}


# ════════════════════════════════════════════════════════════════════════════ #
# Data models                                                                  #
# ════════════════════════════════════════════════════════════════════════════ #


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


# ════════════════════════════════════════════════════════════════════════════ #
# Internal helpers                                                              #
# ════════════════════════════════════════════════════════════════════════════ #


def _is_flatsat_port(p) -> bool:
    """Check if a serial port belongs to a FlatSat device by VID/PID or string signatures."""
    if getattr(p, "vid", None) == USB_VID and getattr(p, "pid", None) == USB_PID:
        return True
    hwid = (getattr(p, "hwid", "") or "").upper()
    if "1209" in hwid and "BABC" in hwid:
        return True
    desc = (getattr(p, "description", "") or "").upper()
    prod = (getattr(p, "product", "") or "").upper()
    for kw in ("FLATSAT", "CATSNIFFER", "ELECTRONIC CATS", "CAT-SHELL", "CAT-RADIO"):
        if kw in desc or kw in prod:
            return True
    return False


def _normalize_port_path(path: str) -> str:
    """Normalize Windows COM port paths — COM10+ must use the \\\\.\\COMx prefix."""
    if sys.platform == "win32" and path:
        path_upper = path.upper()
        if path_upper.startswith("COM") and not path_upper.startswith(r"\\.\COM"):
            try:
                if int(path_upper[3:]) >= 10:
                    return rf"\\.\{path_upper}"
            except ValueError:
                pass
    return path


def _port_sort_key(port):
    """Natural sort on port device name (COM3 < COM10 < COM11)."""
    device = getattr(port, "device", "") or ""
    m = re.search(r"(\d+)", device)
    return (0, int(m.group(1))) if m else (1, device.lower())


def _extract_serial_number(hwid: str) -> str | None:
    """Extract serial number from HWID string (SER=XXXX or SER:XXXX)."""
    if not hwid:
        return None
    m = re.search(r"SER[=:]([A-Za-z0-9_-]+)", hwid)
    return m.group(1) if m else None


def _group_ports_by_device(cat_ports: list) -> dict[str, list]:
    """Group pyserial ListPortInfo entries by physical device.

    Key priority (mirrors catnip _group_ports_by_device):
        1. SER= serial number from HWID string.
        2. port.serial_number attribute.
        3. USB location *prefix* (bus-hub.port part before the first ':').
           Using only the prefix is critical — the interface index after ':'
           differs per port, so using the full string creates one group per port.
    """
    groups: dict[str, list] = {}

    for port in cat_ports:
        key = "unknown"

        if port.hwid and isinstance(port.hwid, str):
            m = re.search(r"SER[=:]([A-Za-z0-9_-]+)", port.hwid)
            if m and m.group(1).upper() != "UNKNOWN":
                key = m.group(1)
            elif port.serial_number and isinstance(port.serial_number, str):
                key = port.serial_number
        elif port.serial_number and isinstance(port.serial_number, str):
            key = port.serial_number

        # Location fallback — only the prefix before ':' so all interfaces of
        # the same device share the same key.
        if key == "unknown" and port.location and isinstance(port.location, str) and ":" in port.location:
            key = port.location.split(":")[0]

        # Last resort: unique per port (device won't be "complete" but won't crash)
        if key == "unknown":
            key = f"unknown-{port.device}"

        groups.setdefault(str(key), []).append(port)

    return groups


def _map_endpoints(ports: list) -> dict[str, str]:
    """Map a group of same-device ports to {endpoint_name: device_path}.

    Four strategies in order (mirrors catnip _map_roles):

    1a. Description substring match ('shell', 'radio0', 'radio 0', etc.)
    1b. pyserial 'interface' attribute substring match.
    1c. LOCATION= embedded in HWID string  — the format PySerial uses on Windows:
        'USB VID:PID=1209:BABC SER=... LOCATION=bus-hub:x.N'
        where N is the USB interface index (0, 2, 4).
    2.  port.location field interface index ('bus-port:config.N' → N).
    3.  Positional fallback on sorted device path (Radio0, Radio1, Shell order).
    """
    result: dict[str, str] = {}

    # Strategy 1a — description substring
    for port in ports:
        desc = str(getattr(port, "description", "") or "").lower()
        for kw, ep in _DESC_TO_ENDPOINT.items():
            if kw in desc and ep not in result:
                result[ep] = str(port.device)
                break

    # Strategy 1b — pyserial 'interface' attribute
    if len(result) < 3:
        _intf_kw = {
            "shell":  ENDPOINT_SHELL,
            "radio0": ENDPOINT_RADIO0,
            "radio1": ENDPOINT_RADIO1,
            "lora":   ENDPOINT_RADIO0,   # CatSniffer LoRa → Radio0 fallback
            "bridge": ENDPOINT_RADIO1,   # CatSniffer Bridge → Radio1 fallback
        }
        for port in ports:
            intf_name = str(getattr(port, "interface", None) or "").lower()
            for kw, ep in _intf_kw.items():
                if kw in intf_name and ep not in result:
                    result[ep] = str(port.device)
                    break

    # Strategy 1c — LOCATION= field embedded inside HWID (Windows PySerial format)
    # e.g. "USB VID:PID=1209:BABC SER=E6616408... LOCATION=1-2:x.4"
    # The interface number after the final '.' is the USB interface index.
    if len(result) < 3:
        for port in ports:
            hwid = getattr(port, "hwid", "") or ""
            if not isinstance(hwid, str):
                continue
            m = re.search(r"LOCATION=\S+:(?:\w+)\.(\d+)", hwid, re.IGNORECASE)
            if m:
                ep = _INTF_TO_ENDPOINT.get(int(m.group(1)))
                if ep and ep not in result:
                    result[ep] = str(port.device)

    # Strategy 2 — port.location interface index
    if len(result) < 3:
        for port in ports:
            if not (port.location and ":" in port.location):
                continue
            try:
                intf_idx = int(port.location.split(":")[-1].split(".")[-1])
                ep = _INTF_TO_ENDPOINT.get(intf_idx)
                if ep and ep not in result:
                    result[ep] = port.device
            except (ValueError, IndexError):
                pass

    # Strategy 3 — positional fallback (sorted COM name)
    if len(result) < 3:
        role_order = [ENDPOINT_RADIO0, ENDPOINT_RADIO1, ENDPOINT_SHELL]
        used_paths = set(result.values())
        role_idx = 0
        for port in sorted(ports, key=_port_sort_key):
            if port.device in used_paths:
                continue
            while role_idx < len(role_order) and role_order[role_idx] in result:
                role_idx += 1
            if role_idx >= len(role_order):
                break
            result[role_order[role_idx]] = port.device
            used_paths.add(port.device)
            role_idx += 1

    return result


# ════════════════════════════════════════════════════════════════════════════ #
# Public API                                                                    #
# ════════════════════════════════════════════════════════════════════════════ #


def discover_devices() -> list[DiscoveredDevice]:
    """Discover all connected FlatSat devices by VID/PID and string signatures."""
    all_ports = list(serial.tools.list_ports.comports())
    cat_ports = [p for p in all_ports if _is_flatsat_port(p)]
    if not cat_ports:
        return []

    cat_ports.sort(key=_port_sort_key)
    groups = _group_ports_by_device(cat_ports)
    devices = []

    for _key, ports in sorted(groups.items()):
        ports.sort(key=_port_sort_key)
        identity = DeviceIdentity(serial_number=_key)
        endpoint_map = _map_endpoints(ports)
        # Normalize COM port paths for Windows (COM10+ → \\.\ prefix)
        normalized_map = {k: _normalize_port_path(v) for k, v in endpoint_map.items()}
        devices.append(DiscoveredDevice(identity=identity, ports=normalized_map))

    return devices
