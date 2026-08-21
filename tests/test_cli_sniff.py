import json
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli
from modules.core.ccsds import build_tm


@patch("modules.core.session.get_device_or_exit")
def test_sniff_radio1_not_available(mock_get_dev):
    mock_dev = MagicMock()
    mock_dev.has_radio1 = False
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["sniff", "-r", "1"])

    assert result.exit_code == 0
    assert "Radio 1 is not physically available" in result.output


@patch("modules.core.session.get_device_or_exit")
def test_sniff_count_limit_and_json_output(mock_get_dev, tmp_path):
    mock_dev = MagicMock()
    mock_dev.has_radio1 = True
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"

    # Build a valid CCSDS TM frame (Heartbeat APID 0x001)
    tm_frame = build_tm(0x001, b"\x01\x02\x03\x04")
    tm_hex = tm_frame.hex().upper()

    rx_line = f"RX: {tm_hex} | RSSI: -45 | SNR: 9"
    mock_dev.read_line_from_radio.return_value = rx_line
    mock_get_dev.return_value = mock_dev

    out_file = tmp_path / "capture.json"

    runner = CliRunner()
    result = runner.invoke(cli, ["sniff", "-n", "2", "-o", str(out_file)])

    assert result.exit_code == 0
    assert "#1: TM APID=0x001" in result.output
    assert "#2: TM APID=0x001" in result.output
    assert out_file.exists()

    with open(out_file, "r") as f:
        data = json.load(f)
    assert len(data["frames"]) == 2
    assert data["frames"][0]["apid"] == 1
    assert data["frames"][0]["rssi"] == -45
    assert data["frames"][0]["snr"] == 9


@patch("modules.core.session.get_device_or_exit")
def test_sniff_keyboard_interrupt(mock_get_dev):
    mock_dev = MagicMock()
    mock_dev.has_radio1 = True
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_dev.read_line_from_radio.side_effect = KeyboardInterrupt()
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["sniff", "-t", "10"])

    assert result.exit_code == 0
    assert "Sniffing stopped by user" in result.output


@patch("modules.core.session.get_device_or_exit")
def test_sniff_no_frames_warning(mock_get_dev):
    mock_dev = MagicMock()
    mock_dev.has_radio1 = True
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_dev.read_line_from_radio.return_value = None
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["sniff", "-t", "0.05"])

    assert result.exit_code == 0
    assert "No CCSDS frames captured" in result.output
