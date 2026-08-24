from unittest.mock import MagicMock, patch

from core.constants import (
    ENDPOINT_RADIO0,
    ENDPOINT_RADIO1,
    ENDPOINT_SHELL,
    DeviceHealth,
)
from core.serial_manager import (
    DeviceIdentity,
    DiscoveredDevice,
    _extract_serial_number,
    _group_ports_by_device,
    _map_endpoints,
    discover_devices,
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
    result = _map_endpoints(ports)
    assert result[ENDPOINT_RADIO0] == "/dev/ttyACM0"
    assert result[ENDPOINT_RADIO1] == "/dev/ttyACM1"
    assert result[ENDPOINT_SHELL] == "/dev/ttyACM2"


def test_map_endpoints_positional_fallback():
    ports = [
        MagicMock(device="/dev/ttyACM0", description="Unknown CDC"),
        MagicMock(device="/dev/ttyACM1", description="Unknown CDC"),
        MagicMock(device="/dev/ttyACM2", description="Unknown CDC"),
    ]
    result = _map_endpoints(ports)
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


def test_group_ports_by_device_using_serial_number():
    p1 = MagicMock(serial_number="ABC123", hwid="SER=UNKNOWN", device="/dev/ttyACM0", location=None)
    p2 = MagicMock(serial_number="ABC123", hwid="SER=UNKNOWN", device="/dev/ttyACM1", location=None)
    p3 = MagicMock(serial_number="XYZ789", hwid="SER=UNKNOWN", device="/dev/ttyACM2", location=None)
    groups = _group_ports_by_device([p1, p2, p3])
    assert len(groups) == 2
    assert len(groups["ABC123"]) == 2
    assert len(groups["XYZ789"]) == 1

