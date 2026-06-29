"""USB serial device discovery for FlatSat ground station.

Discovers FlatSat devices by VID/PID (0x1209:0xBABC), groups 3 CDC
endpoints per device by serial number, and maps them to Radio0/Radio1/Shell.
Adapted from flatsatTUI/discovery.py.
"""

import re
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
    match = re.search(r"SER=([A-Za-z0-9]+)", hwid)
    return match.group(1) if match else None


def _extract_interface_number(port) -> int | None:
    """Extract USB interface number from port attributes."""
    hwid = getattr(port, "hwid", "") or ""
    if not isinstance(hwid, str):
        hwid = ""
    hwid = hwid.upper()
    
    # Windows style: VID_1209&PID_BABC&MI_02
    match = re.search(r"MI_(\d+)", hwid)
    if match:
        return int(match.group(1))
        
    # Alternate Windows / general style: MI=02
    match = re.search(r"MI=(\d+)", hwid)
    if match:
        return int(match.group(1))

    # Linux / macOS style in location or hwid: e.g. "1-7:1.2" or "LOCATION=1-7:1.2"
    location = getattr(port, "location", "") or ""
    if not isinstance(location, str):
        location = ""
    for string_to_check in [location, hwid]:
        if string_to_check:
            # Match :config.interface, e.g. :1.2 or :1.0
            match = re.search(r":\d+\.(\d+)(?:$|\s)", string_to_check)
            if match:
                return int(match.group(1))
                
    return None


def _group_ports_by_device(ports: list) -> dict[str, list]:
    """Group ports by device serial number."""
    groups: dict[str, list] = {}
    for port in ports:
        serial_num = getattr(port, "serial_number", None)
        if serial_num and isinstance(serial_num, str):
            serial_num = serial_num.strip()
        else:
            serial_num = None

        if not serial_num:
            serial_num = _extract_serial_number(port.hwid) if port.hwid else None
        if not serial_num and hasattr(port, "location") and port.location:
            serial_num = f"loc-{port.location}"
        if not serial_num:
            serial_num = f"unknown-{port.device}"
        groups.setdefault(serial_num, []).append(port)
    return groups


def _map_endpoints_intelligent(ports: list) -> dict[str, str]:
    """Map ports to endpoint names using multiple strategies."""
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

    # Strategy 2: match by USB interface number or interface/product strings
    if len(ports_dict) < 3:
        for port in sorted_ports:
            if port.device in ports_dict.values():
                continue
            
            # Check port interface attribute
            if hasattr(port, "interface") and port.interface:
                desc = port.interface.lower()
                if "shell" in desc:
                    ports_dict[ENDPOINT_SHELL] = port.device
                    continue
                elif "radio0" in desc or "radio 0" in desc:
                    ports_dict[ENDPOINT_RADIO0] = port.device
                    continue
                elif "radio1" in desc or "radio 1" in desc:
                    ports_dict[ENDPOINT_RADIO1] = port.device
                    continue

            # Check port product attribute
            if hasattr(port, "product") and port.product:
                desc = port.product.lower()
                if "shell" in desc:
                    ports_dict[ENDPOINT_SHELL] = port.device
                    continue
                elif "radio0" in desc or "radio 0" in desc:
                    ports_dict[ENDPOINT_RADIO0] = port.device
                    continue
                elif "radio1" in desc or "radio 1" in desc:
                    ports_dict[ENDPOINT_RADIO1] = port.device
                    continue

            # Check raw USB interface number
            interface_num = _extract_interface_number(port)
            if interface_num is not None:
                # Interface 0/1 -> Radio 0, Interface 2/3 -> Radio 1, Interface 4/5 -> Shell
                if interface_num in (0, 1):
                    ports_dict[ENDPOINT_RADIO0] = port.device
                elif interface_num in (2, 3):
                    ports_dict[ENDPOINT_RADIO1] = port.device
                elif interface_num in (4, 5):
                    ports_dict[ENDPOINT_SHELL] = port.device

    # Strategy 3: positional fallback
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
