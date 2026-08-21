import pytest
from unittest.mock import MagicMock, patch
import click
from modules.core.constants import ENDPOINT_SHELL, ENDPOINT_RADIO0, ENDPOINT_RADIO1
from modules.core.serial_manager import DeviceIdentity, DiscoveredDevice
from modules.core.session import (
    _match_device,
    flatsat_get_devices,
    get_device_or_exit,
    get_selected_device,
    send_cmd,
    with_device,
)


def _make_mock_discovered(serial="FS001", shell="/dev/ttyACM2", radio0="/dev/ttyACM0", radio1="/dev/ttyACM1"):
    return DiscoveredDevice(
        identity=DeviceIdentity(serial_number=serial),
        ports={
            ENDPOINT_RADIO0: radio0,
            ENDPOINT_RADIO1: radio1,
            ENDPOINT_SHELL: shell,
        },
    )


def test_match_device_by_index():
    dev0 = _make_mock_discovered("DEV0")
    dev1 = _make_mock_discovered("DEV1")
    devs = [dev0, dev1]

    assert _match_device(devs, "0") == dev0
    assert _match_device(devs, 0) == dev0
    assert _match_device(devs, "1") == dev1
    assert _match_device(devs, "5") is None


def test_match_device_by_serial():
    dev0 = _make_mock_discovered("FS_ALPHA")
    dev1 = _make_mock_discovered("FS_BETA")
    devs = [dev0, dev1]

    assert _match_device(devs, "FS_ALPHA") == dev0
    assert _match_device(devs, "fs_alpha") == dev0  # Case-insensitive
    assert _match_device(devs, "UNKNOWN") is None


@patch("modules.core.session.discover_devices")
def test_flatsat_get_devices(mock_discover):
    mock_discover.return_value = [_make_mock_discovered("FS001")]
    res = flatsat_get_devices()
    assert len(res) == 1
    assert res[0].identity.serial_number == "FS001"


@patch("modules.core.session.flatsat_get_devices")
def test_get_selected_device_direct_port(mock_get_devs):
    # Direct port should work regardless of discovered devices
    mock_get_devs.return_value = [_make_mock_discovered("FS001")]
    dev = get_selected_device(port="/dev/ttyUSB9")
    assert dev.serial_number == "direct"


@patch("modules.core.session.flatsat_get_devices")
def test_get_selected_device_none_connected_exits(mock_get_devs):
    mock_get_devs.return_value = []
    with pytest.raises(SystemExit) as exc:
        get_selected_device()
    assert exc.value.code == 1


@patch("modules.core.session.flatsat_get_devices")
def test_get_selected_device_single_auto_select(mock_get_devs):
    d = _make_mock_discovered("FS_SINGLE")
    mock_get_devs.return_value = [d]
    dev = get_selected_device()
    assert dev.serial_number == "FS_SINGLE"


@patch("modules.core.session.flatsat_get_devices")
def test_get_selected_device_multiple_without_selector_exits(mock_get_devs):
    mock_get_devs.return_value = [_make_mock_discovered("FS1"), _make_mock_discovered("FS2")]
    with pytest.raises(SystemExit) as exc:
        get_selected_device()
    assert exc.value.code == 1


@patch("modules.core.session.flatsat_get_devices")
def test_get_selected_device_by_selector_success(mock_get_devs):
    d1 = _make_mock_discovered("FS1")
    d2 = _make_mock_discovered("FS2")
    mock_get_devs.return_value = [d1, d2]

    dev = get_selected_device(device="FS2")
    assert dev.serial_number == "FS2"

    dev_by_idx = get_selected_device(device="0")
    assert dev_by_idx.serial_number == "FS1"


@patch("modules.core.session.flatsat_get_devices")
def test_get_selected_device_invalid_selector_exits(mock_get_devs):
    mock_get_devs.return_value = [_make_mock_discovered("FS1")]
    with pytest.raises(SystemExit) as exc:
        get_selected_device(device="NONEXISTENT")
    assert exc.value.code == 1


@patch("modules.core.session.get_selected_device")
def test_get_device_or_exit_connect_fails(mock_get_sel):
    mock_dev = MagicMock()
    mock_dev.connect.return_value = {"shell": False}
    mock_get_sel.return_value = mock_dev

    with pytest.raises(SystemExit) as exc:
        get_device_or_exit()
    assert exc.value.code == 1


@patch("modules.core.session.get_selected_device")
def test_get_device_or_exit_connect_success(mock_get_sel):
    mock_dev = MagicMock()
    mock_dev.connect.return_value = {"shell": True}
    mock_get_sel.return_value = mock_dev

    dev = get_device_or_exit()
    assert dev == mock_dev


@patch("modules.core.session.get_device_or_exit")
def test_with_device_decorator_flow(mock_get_dev):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    called_with = []

    @click.command()
    @with_device
    def sample_cmd(dev):
        called_with.append(dev)
        return "success"

    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(sample_cmd, [])

    assert result.exit_code == 0
    assert len(called_with) == 1
    assert called_with[0] == mock_dev
    mock_dev.disconnect.assert_called_once()


@patch("modules.core.session.get_device_or_exit")
def test_with_device_decorator_disconnects_on_exception(mock_get_dev):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    @click.command()
    @with_device
    def failing_cmd(dev):
        raise ValueError("test failure")

    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(failing_cmd, [])

    assert result.exit_code != 0
    mock_dev.disconnect.assert_called_once()


def test_send_cmd_echo_stripping():
    dev = MagicMock()

    # Exact echo
    dev.send_shell_command_full.return_value = "status\r\nOK\r\nState: nominal"
    assert send_cmd(dev, "status") == "OK\nState: nominal"

    # Labeled firmware responses
    dev.send_shell_command_full.return_value = "difficulty: 1 (normal)"
    assert send_cmd(dev, "difficulty") == "difficulty: 1 (normal)"

    dev.send_shell_command_full.return_value = "flight: NOMINAL"
    assert send_cmd(dev, "flight") == "flight: NOMINAL"

    # Concatenated echo
    dev.send_shell_command_full.return_value = "flightflight: NOMINAL"
    assert send_cmd(dev, "flight") == "flight: NOMINAL"

    # No echo at all
    dev.send_shell_command_full.return_value = "Batt: 4200mV"
    assert send_cmd(dev, "status") == "Batt: 4200mV"

    # None / empty response
    dev.send_shell_command_full.return_value = None
    assert send_cmd(dev, "status") is None

    dev.send_shell_command_full.return_value = ""
    assert send_cmd(dev, "status") is None
