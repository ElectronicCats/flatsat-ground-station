"""Regression tests for CLI hardening: exit codes, role detection, input validation."""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from modules.core.ccsds import build_tm
from modules.core.cli import _bump_seq, _detect_local_role, _first_subcommand, _load_frames, cli, main

# ==============================================================================
# P1-1: replay must not crash on truncated frames
# ==============================================================================

def test_bump_seq_rejects_short_frame():
    """A frame too short for a primary header raises ValueError, not struct.error."""
    for short in (b"", b"\xaa", b"\xaa\xbb\xcc"):
        try:
            _bump_seq(short, 0)
        except ValueError as exc:
            assert "need at least" in str(exc)
        else:
            raise AssertionError(f"{short!r} should have been rejected")


def test_load_frames_drops_unusable_entries(tmp_path):
    """Short, odd-length and non-hex entries are dropped, valid ones survive."""
    good = build_tm(0x001, b"\x01").hex().upper()
    capture = tmp_path / "capture.json"
    capture.write_text(
        json.dumps(
            {
                "frames": [
                    {"hex": good},
                    {"hex": "AABBCC"},          # 3 bytes: too short
                    {"hex": "AABB"},             # odd length
                    {"hex": "ZZZZ"},             # not hex
                    {"hex": ""},                 # empty
                ]
            }
        )
    )

    hexes, skipped = _load_frames(str(capture))
    assert hexes == [good]
    assert skipped == 4


def test_load_frames_text_log_rejects_unusable_lines(tmp_path):
    """Text captures drop unusable lines: sub-6-byte noise is ignored at parse
    time (a bare word like "add" is valid hex, so it must not be reported as a
    frame), while an odd-length line long enough to look like a frame is counted."""
    good = build_tm(0x001, b"\x02").hex().upper()
    log = tmp_path / "frames.txt"
    # 6-char hex noise (< 12 chars) is ignored; a 13-char odd-length run is
    # queued and then rejected by the validator.
    log.write_text(f"# header\nAABBCC\nAABBCCDDEEFFA\n{good}\n")

    hexes, skipped = _load_frames(str(log))
    assert hexes == [good]
    assert skipped == 1


def test_load_frames_json_counts_every_dropped_entry(tmp_path):
    """For JSON captures every unusable entry is reported, including non-strings."""
    good = build_tm(0x001, b"\x01").hex().upper()
    capture = tmp_path / "capture.json"
    capture.write_text(
        json.dumps(
            {
                "frames": [
                    {"hex": good},
                    {"hex": "AABBCC"},   # 3 bytes: too short
                    {"hex": "AABB"},      # odd length
                    {"hex": "ZZZZ"},      # not hex
                    {"hex": ""},          # empty
                    {"hex": 12345},       # not a string at all
                    "not-a-dict",
                ]
            }
        )
    )

    hexes, skipped = _load_frames(str(capture))
    assert hexes == [good]
    assert skipped == 6


@patch("time.sleep", return_value=None)
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_replay_modify_seq_skips_truncated_frame(mock_get_dev, mock_send_raw, mock_sleep, tmp_path):
    """A capture mixing a truncated frame with a good one replays the good one."""
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_raw.return_value = {"status": "sent", "bytes": 16, "response": "OK"}

    good = build_tm(0x001, b"\x01").hex().upper()
    capture = tmp_path / "capture.json"
    capture.write_text(json.dumps({"frames": [{"hex": "AABBCC"}, {"hex": good}]}))

    runner = CliRunner()
    result = runner.invoke(cli, ["replay", str(capture), "--modify-seq"])

    assert result.exit_code == 0
    assert "Skipped 1 unusable frame" in result.output
    assert "Replayed 1/1 frames." in result.output
    assert mock_send_raw.call_count == 1


@patch("time.sleep", return_value=None)
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_replay_reports_failed_frames(mock_get_dev, mock_send_raw, mock_sleep, tmp_path):
    """A frame the radio rejected makes the command exit non-zero."""
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_raw.return_value = {"status": "error", "error": "Radio timeout"}

    capture = tmp_path / "capture.json"
    capture.write_text(json.dumps({"frames": [{"hex": build_tm(0x001, b"\x01").hex().upper()}]}))

    runner = CliRunner()
    result = runner.invoke(cli, ["replay", str(capture)])

    assert result.exit_code == 1
    assert "Radio timeout" in result.output
    assert "Replayed 0/1 frames (1 failed)." in result.output


# ==============================================================================
# P2-5: role detection must not fail open to ground_station
# ==============================================================================

def test_detect_local_role_satellite():
    dev = MagicMock()
    dev.send_shell_command_full.side_effect = lambda cmd: "mode: satellite" if cmd == "mode" else "ok"
    assert _detect_local_role(dev) == "satellite"


def test_detect_local_role_ground_station():
    dev = MagicMock()
    dev.send_shell_command_full.side_effect = lambda cmd: "mode: gs" if cmd == "mode" else "Radio0: LoRa  mode=command"
    assert _detect_local_role(dev) == "ground_station"


def test_detect_local_role_unknown_when_queries_fail():
    """Silent mode/status must NOT be reported as ground_station."""
    dev = MagicMock()
    dev.has_radio1 = True
    dev.send_shell_command_full.return_value = None
    assert _detect_local_role(dev) == "unknown"


def test_detect_local_role_unknown_on_unrecognised_mode():
    dev = MagicMock()
    dev.has_radio1 = True
    dev.send_shell_command_full.side_effect = lambda cmd: "mode: wat" if cmd == "mode" else "State: NOMINAL"
    assert _detect_local_role(dev) == "unknown"


def test_detect_local_role_streaming_radio_is_not_ground_station():
    """A streaming radio with an unreadable mode is ambiguous, not a ground station."""
    dev = MagicMock()
    dev.has_radio1 = True
    dev.send_shell_command_full.side_effect = lambda cmd: None if cmd == "mode" else "Radio0: LoRa  mode=stream"
    assert _detect_local_role(dev) == "unknown"


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_flight_refuses_to_guess_role(mock_get_dev, mock_send_cmd):
    """A board whose mode/status queries go unanswered must not be guessed as a GS."""
    mock_dev = MagicMock()
    mock_dev.has_radio1 = True
    mock_dev.send_shell_command_full.return_value = None
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["flight", "safe"])

    assert result.exit_code == 1
    assert "Could not tell whether this board is a satellite or a ground station" in result.output
    assert "--role" in result.output
    # Neither set locally nor transmitted over RF.
    mock_send_cmd.assert_not_called()


@patch("modules.core.cli._detect_local_role", return_value="unknown")
@patch("modules.core.cli._send_flight_over_rf")
@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_flight_role_override_satellite(mock_get_dev, mock_send_cmd, mock_send_rf, mock_detect):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["flight", "safe", "--role", "satellite"])

    assert result.exit_code == 0
    mock_send_cmd.assert_called_once_with(mock_dev, "flight safe")
    mock_detect.assert_not_called()
    mock_send_rf.assert_not_called()


@patch("modules.core.cli._detect_local_role", return_value="unknown")
@patch("modules.core.cli._send_flight_over_rf")
@patch("modules.core.session.get_device_or_exit")
def test_flight_role_override_ground_station(mock_get_dev, mock_send_rf, mock_detect):
    mock_dev = MagicMock()
    mock_dev.send_shell_command_full.return_value = "difficulty: 0"
    mock_get_dev.return_value = mock_dev
    mock_send_rf.return_value = {"status": "sent", "bytes": 16, "response": "OK"}

    runner = CliRunner()
    result = runner.invoke(cli, ["flight", "safe", "--role", "ground_station"])

    assert result.exit_code == 0
    assert "Sending flight TC 'safe' over RF" in result.output
    mock_detect.assert_not_called()
    mock_send_rf.assert_called_once_with(mock_dev, "safe", 0)


def test_flight_rejects_invalid_role():
    runner = CliRunner()
    result = runner.invoke(cli, ["flight", "safe", "--role", "nonsense"])
    assert result.exit_code == 2


# ==============================================================================
# P2-8: option values are validated before reaching the board shell
# ==============================================================================

@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_profile_rejects_shell_injection(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["mode", "tinygs", "--profile", "evil reboot\nlora_power ALL 22"])

    assert result.exit_code == 2
    assert "may only contain letters, digits" in result.output
    mock_send_cmd.assert_not_called()


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_config_syncword_rejects_shell_injection(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev

    runner = CliRunner()
    result = runner.invoke(cli, ["config", "--syncword", "0x2D reboot"])

    assert result.exit_code == 2
    assert "may only contain letters, digits" in result.output
    mock_send_cmd.assert_not_called()


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_config_syncword_accepts_documented_values(mock_get_dev, mock_send_cmd):
    for value in ("public", "private", "0x2D"):
        mock_send_cmd.reset_mock()
        mock_send_cmd.return_value = "OK"
        mock_dev = MagicMock()
        mock_get_dev.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--syncword", value, "--apply"])

        assert result.exit_code == 0, f"{value} should be accepted"
        mock_send_cmd.assert_any_call(mock_dev, f"lora_syncword R0 {value}")


@patch("modules.core.cli.send_cmd")
@patch("modules.core.session.get_device_or_exit")
def test_mode_profile_accepts_underscores_and_digits(mock_get_dev, mock_send_cmd):
    mock_dev = MagicMock()
    mock_get_dev.return_value = mock_dev
    mock_send_cmd.return_value = "OK"

    runner = CliRunner()
    result = runner.invoke(cli, ["mode", "tinygs", "--profile", "my_sat-2.0"])

    assert result.exit_code == 0
    mock_send_cmd.assert_any_call(mock_dev, "tinygs spoof my_sat-2.0")


# ==============================================================================
# P1-4: banner labels the subcommand, not an option value
# ==============================================================================

def test_first_subcommand_ignores_option_values():
    assert _first_subcommand(["-d", "0", "status"]) == "status"
    assert _first_subcommand(["--device", "0", "--port", "/dev/ttyACM0", "mode", "gs"]) == "mode"
    assert _first_subcommand(["config", "--freq", "915000000"]) == "config"
    assert _first_subcommand(["--help"]) is None
    assert _first_subcommand([]) is None


@patch("modules.core.cli.print_banner")
@patch("modules.core.cli.send_cmd", return_value=None)
@patch("modules.core.session.get_device_or_exit")
def test_main_banner_uses_subcommand_name(mock_get_dev, mock_send_cmd, mock_banner):
    """`flatsat -d 0 status` must label the banner "status", not the device index."""
    mock_get_dev.return_value = MagicMock()

    with patch("sys.argv", ["flatsat", "-d", "0", "status"]), patch.dict("os.environ", {}, clear=True):
        try:
            main()
        except SystemExit:
            pass  # the board is not answering; the banner is what matters here

    mock_banner.assert_called_once_with("status")


# ==============================================================================
# Misc option bounds
# ==============================================================================

@patch("modules.core.session.get_device_or_exit")
def test_sniff_rejects_negative_count(mock_get_dev):
    runner = CliRunner()
    result = runner.invoke(cli, ["sniff", "-n", "-1"])
    assert result.exit_code == 2
