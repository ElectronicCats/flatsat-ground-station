from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli
from modules.core.ccsds import build_tc


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_transmit_raw_hex(mock_get_dev, mock_send_raw):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_raw.return_value = {"status": "sent", "bytes": 6, "response": "OK"}

    runner = CliRunner()
    result = runner.invoke(cli, ["transmit", "1AF0C30500AB"])

    assert result.exit_code == 0
    assert "Transmitting 6 bytes from hex string" in result.output
    assert "sent (6 bytes, OK)" in result.output
    mock_send_raw.assert_called_once_with(bytes.fromhex("1AF0C30500AB"))


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_transmit_text(mock_get_dev, mock_send_raw):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_raw.return_value = {"status": "sent_simulated", "bytes": 9}

    runner = CliRunner()
    result = runner.invoke(cli, ["transmit", "--text", "HELLO SAT"])

    assert result.exit_code == 0
    assert "Transmitting 9 bytes from text string" in result.output
    assert "transmitted in simulated mode" in result.output
    mock_send_raw.assert_called_once_with(b"HELLO SAT")


@patch("modules.core.session.get_device_or_exit")
def test_transmit_invalid_hex(mock_get_dev):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["transmit", "INVALID_HEX_DATA"])

    assert result.exit_code == 0
    assert "Invalid hex string. Use --text" in result.output


@patch("modules.core.session.get_device_or_exit")
def test_transmit_empty_payload(mock_get_dev):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["transmit", "--text", ""])

    assert result.exit_code == 0
    assert "Empty payload, nothing to transmit" in result.output


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_transmit_with_protect(mock_get_dev, mock_send_raw):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 1"
    mock_get_dev.return_value = mock_dev
    mock_send_raw.return_value = {"status": "sent", "bytes": 16, "response": "OK"}

    runner = CliRunner()
    result = runner.invoke(cli, ["transmit", "--text", "PING", "--protect"])

    assert result.exit_code == 0
    assert "SDLS level 1" in result.output
    # Verify sent payload was wrapped into TC frame with secondary header & CRC
    assert mock_send_raw.call_count == 1
    sent_frame = mock_send_raw.call_args[0][0]
    assert len(sent_frame) >= 12


@patch("time.sleep", return_value=None)
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_transmit_repeat_and_delay(mock_get_dev, mock_send_raw, mock_sleep):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_raw.return_value = {"status": "sent", "bytes": 4, "response": "OK"}

    runner = CliRunner()
    result = runner.invoke(cli, ["transmit", "AABBCCDD", "--repeat", "3", "--delay", "0.5"])

    assert result.exit_code == 0
    assert "Transmitted payload 3/3 times." in result.output
    assert mock_send_raw.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(0.5)
