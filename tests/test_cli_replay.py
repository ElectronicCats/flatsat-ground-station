import json
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from modules.core.cli import cli, _bump_seq
from modules.core.ccsds import build_tm, parse_frame


def test_bump_seq():
    tm = build_tm(0x001, b"\xAA\xBB", seq_count=5)
    new_frame, old_seq, new_seq = _bump_seq(tm, 0)
    assert old_seq == 5
    assert new_seq == 1005
    pkt = parse_frame(new_frame)
    assert pkt.seq_count == 1005
    assert pkt.crc_valid


@patch("time.sleep", return_value=None)
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_replay_from_json(mock_get_dev, mock_send_raw, mock_sleep, tmp_path):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_raw.return_value = {"status": "sent", "bytes": 16, "response": "OK"}

    f1 = build_tm(0x001, b"\x01").hex().upper()
    f2 = build_tm(0x001, b"\x02").hex().upper()

    capture_path = tmp_path / "capture.json"
    with open(capture_path, "w") as f:
        json.dump({"frames": [{"hex": f1}, {"hex": f2}]}, f)

    runner = CliRunner()
    result = runner.invoke(cli, ["replay", str(capture_path)])

    assert result.exit_code == 0
    assert "Loaded 2 frames" in result.output
    assert "Replayed 2/2 frames." in result.output
    assert mock_send_raw.call_count == 2


@patch("time.sleep", return_value=None)
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_replay_from_raw_hex_lines(mock_get_dev, mock_send_raw, mock_sleep, tmp_path):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_raw.return_value = {"status": "sent", "bytes": 16, "response": "OK"}

    f1 = build_tm(0x001, b"\x01").hex().upper()
    f2 = build_tm(0x001, b"\x02").hex().upper()

    raw_path = tmp_path / "frames.txt"
    raw_path.write_text(f"# Log file\n{f1}\nRX: {f2} | RSSI: -50\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["replay", str(raw_path), "--modify-seq"])

    assert result.exit_code == 0
    assert "Loaded 2 frames" in result.output
    assert "Replayed 2/2 frames." in result.output


@patch("modules.core.session.get_device_or_exit")
def test_replay_empty_file(mock_get_dev, tmp_path):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    empty_path = tmp_path / "empty.json"
    empty_path.write_text("{}")

    runner = CliRunner()
    result = runner.invoke(cli, ["replay", str(empty_path)])

    assert result.exit_code == 0
    assert "No frames found in" in result.output
