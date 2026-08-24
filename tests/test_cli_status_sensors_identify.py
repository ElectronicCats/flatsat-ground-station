from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_status_command_success(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.side_effect = lambda dev, cmd: {
        "fw_version": "FW: v1.0.0 (clean)",
        "status": "State: NOMINAL | Batt: 4100mV",
    }.get(cmd)

    runner = CliRunner()
    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "SYSTEM STATUS" in result.output
    assert "FW: v1.0.0" in result.output
    assert "NOMINAL" in result.output
    assert mock_send_cmd.call_count == 2


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_status_command_empty_warning(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = None

    runner = CliRunner()
    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "No status response received" in result.output


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_sensors_command_success(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "Accel: x=10 y=0 z=1000 mg\nTemp: 24.5 C\nPress: 1013.25 hPa"

    runner = CliRunner()
    result = runner.invoke(cli, ["sensors"])

    assert result.exit_code == 0
    assert "TELEMETRY SENSORS" in result.output
    assert "Accel: x=10" in result.output
    assert "24.5 C" in result.output


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_sensors_command_failure(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = None

    runner = CliRunner()
    result = runner.invoke(cli, ["sensors"])

    assert result.exit_code == 0
    assert "Failed to retrieve sensor values" in result.output


@patch("time.sleep", return_value=None)
@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_identify_command(mock_get_dev, mock_send_cmd, mock_sleep):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["identify"])

    assert result.exit_code == 0
    assert "Identifying FlatSat board" in result.output
    assert "LED identification sequence completed" in result.output
    mock_send_cmd.assert_called_once_with(mock_dev, "identify")
    mock_sleep.assert_called_once_with(2.2)
