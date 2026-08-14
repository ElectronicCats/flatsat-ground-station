from unittest.mock import MagicMock, patch

from core.constants import ENDPOINT_RADIO0, ENDPOINT_RADIO1, ENDPOINT_SHELL
from core.device import FlatSatDevice, parse_lora_rx
from core.serial_manager import DeviceIdentity, DiscoveredDevice


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


@patch("core.device.os.path.exists", return_value=True)
@patch("core.device.serial.Serial")
def test_send_shell_command(mock_serial_cls, mock_exists):
    mock_ser = MagicMock()
    mock_ser.in_waiting = 4
    mock_ser.read.return_value = b"OK\r\n"
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


@patch("core.device.os.path.exists", return_value=True)
@patch("core.device.serial.Serial")
def test_partial_connect_not_connected(mock_serial_cls, mock_exists):
    """is_connected requires ALL three ports open, not just any."""
    import serial

    ser_r0 = MagicMock()
    ser_r0.open.side_effect = serial.SerialException("port busy")
    ser_r1 = MagicMock()
    ser_shell = MagicMock()

    mock_serial_cls.side_effect = [ser_r0, ser_r1, ser_shell]

    disc = _make_discovered()
    dev = FlatSatDevice(disc)
    result = dev.connect()
    assert result["radio0"] is False
    assert result["radio1"] is False
    assert result["shell"] is False
    assert not dev.is_connected  # partial = not connected




def test_is_connected_paths_check():
    class DummySerial:
        def __init__(self):
            self.is_open = True

    disc = _make_discovered(r0="/dev/nonexistent_r0", sh="/dev/nonexistent_shell")
    dev = FlatSatDevice(disc)
    dev._radio0 = DummySerial()
    dev._shell = DummySerial()

    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = False
        assert not dev.is_connected

        mock_exists.return_value = True
        assert dev.is_connected

