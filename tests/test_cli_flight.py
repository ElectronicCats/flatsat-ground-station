from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli, _detect_local_role


def test_detect_local_role():
    dev_sat = MagicMock()
    dev_sat.send_shell_command_full.side_effect = lambda cmd: "mode: satellite" if cmd == "mode" else "status ok"
    assert _detect_local_role(dev_sat) == "satellite"

    dev_gs = MagicMock()
    dev_gs.send_shell_command_full.side_effect = lambda cmd: "mode: gs" if cmd == "mode" else "Radio0: LoRa  mode=command"
    assert _detect_local_role(dev_gs) == "ground_station"


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_flight_query(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "flight: NOMINAL"

    runner = CliRunner()
    result = runner.invoke(cli, ["flight"])

    assert result.exit_code == 0
    assert "Flight State: flight: NOMINAL" in result.output
    mock_send_cmd.assert_called_once_with(mock_dev, "flight")


@patch("modules.core.cli._detect_local_role", return_value="satellite")
@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_flight_set_on_satellite(mock_get_dev, mock_send_cmd, mock_detect):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["flight", "nominal"])

    assert result.exit_code == 0
    assert "Flight state set to 'nominal'" in result.output
    mock_send_cmd.assert_called_once_with(mock_dev, "flight nominal")


@patch("modules.core.cli._detect_local_role", return_value="ground_station")
@patch("modules.core.cli._send_flight_over_rf")
@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_flight_set_on_ground_station(mock_get_dev, mock_send_cmd, mock_send_rf, mock_detect):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 1"
    mock_get_dev.return_value = mock_dev
    mock_send_rf.return_value = {"status": "sent", "bytes": 16, "response": "OK"}

    runner = CliRunner()
    result = runner.invoke(cli, ["flight", "safe"])

    assert result.exit_code == 0
    assert "Ground station detected. Sending flight TC 'safe' over RF" in result.output
    assert "Flight TC 'safe' transmitted over RF" in result.output
    mock_send_rf.assert_called_once_with(mock_dev, "safe", 1)
    # Ensure no local shell command was sent to ground station
    mock_send_cmd.assert_not_called()


@patch("modules.core.cli._detect_local_role", return_value="ground_station")
@patch("modules.core.cli._send_flight_over_rf")
@patch("modules.core.session.get_device_or_exit")
def test_flight_with_difficulty_override(mock_get_dev, mock_send_rf, mock_detect):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_rf.return_value = {"status": "sent_simulated", "bytes": 16}

    runner = CliRunner()
    result = runner.invoke(cli, ["flight", "debug", "--difficulty", "3"])

    assert result.exit_code == 0
    assert "SDLS level 3" in result.output
    assert "Transmitted in simulated mode" in result.output
    mock_send_rf.assert_called_once_with(mock_dev, "debug", 3)


@patch("modules.core.cli._detect_local_role", return_value="ground_station")
@patch("modules.core.cli._send_flight_over_rf")
@patch("modules.core.session.get_device_or_exit")
def test_flight_rf_error(mock_get_dev, mock_send_rf, mock_detect):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_rf.return_value = {"status": "error", "error": "Radio timeout"}

    runner = CliRunner()
    result = runner.invoke(cli, ["flight", "idle"])

    assert result.exit_code == 0
    assert "Flight TC failed: Radio timeout" in result.output
