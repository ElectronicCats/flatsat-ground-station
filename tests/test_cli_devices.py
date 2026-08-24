from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli
from modules.core.constants import ENDPOINT_RADIO0, ENDPOINT_RADIO1, ENDPOINT_SHELL
from modules.core.serial_manager import DeviceIdentity, DiscoveredDevice


def _mock_discovered(serial="TEST_001", radio0="/dev/ttyACM0", radio1="/dev/ttyACM1", shell="/dev/ttyACM2"):
    ports = {}
    if radio0:
        ports[ENDPOINT_RADIO0] = radio0
    if radio1:
        ports[ENDPOINT_RADIO1] = radio1
    if shell:
        ports[ENDPOINT_SHELL] = shell
    return DiscoveredDevice(identity=DeviceIdentity(serial_number=serial), ports=ports)


@patch("modules.core.cli.flatsat_get_devices")
def test_devices_empty(mock_get_devs):
    mock_get_devs.return_value = []
    runner = CliRunner()
    result = runner.invoke(cli, ["devices"])

    assert result.exit_code == 0
    assert "No FlatSat devices detected" in result.output


@patch("modules.core.cli.flatsat_get_devices")
def test_devices_single_healthy(mock_get_devs):
    mock_get_devs.return_value = [_mock_discovered("DEV_SAT_001")]
    runner = CliRunner()
    result = runner.invoke(cli, ["devices"])

    assert result.exit_code == 0
    assert "DEV_SAT_001" in result.output
    assert "/dev/ttyACM0" in result.output
    assert "/dev/ttyACM1" in result.output
    assert "/dev/ttyACM2" in result.output
    assert "HEALTHY" in result.output


@patch("modules.core.cli.flatsat_get_devices")
def test_devices_multiple(mock_get_devs):
    d1 = _mock_discovered("DEV_GS_001", radio0="/dev/ttyACM0", radio1=None, shell="/dev/ttyACM1")
    d2 = _mock_discovered("DEV_SAT_002", radio0="/dev/ttyACM2", radio1="/dev/ttyACM3", shell="/dev/ttyACM4")
    mock_get_devs.return_value = [d1, d2]

    runner = CliRunner()
    result = runner.invoke(cli, ["devices"])

    assert result.exit_code == 0
    assert "DEV_GS_001" in result.output
    assert "DEV_SAT_002" in result.output
    assert "Found 2 FlatSat device(s)" in result.output


@patch("modules.core.cli.flatsat_get_devices")
def test_devices_partial_health(mock_get_devs):
    d_partial = _mock_discovered("DEV_PARTIAL", radio0=None, radio1=None, shell="/dev/ttyACM0")
    mock_get_devs.return_value = [d_partial]

    runner = CliRunner()
    result = runner.invoke(cli, ["devices"])

    assert result.exit_code == 0
    assert "DEV_PARTIAL" in result.output
    assert "Not found" in result.output
