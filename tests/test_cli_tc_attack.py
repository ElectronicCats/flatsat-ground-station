"""Tests for the generic `tc` telecommand sender and the CTF `attack` suite.

The attack scenarios mirror flat-sat-fw-interno/Attacks/. These tests assert the
APIDs and payloads match that suite, so a firmware-side change is caught here.
"""

import struct
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from modules.core.ccsds import parse_frame
from modules.core.cli import cli
from modules.core.constants import (
    APID_TC_BROADCAST,
    APID_TC_DIAG_MEM,
    APID_TC_GS_AUTH_XOR,
    APID_TC_REPLAY,
    APID_TC_RESETC,
    APID_TC_SET_THRUSTER,
    XOR_KEY,
)

# APIDs the suite relies on but constants.py shares with other telecommands.
APID_RECON_ENUM = 0x000


def _mock_board(mock_get_dev, has_radio1=True, difficulty="difficulty: 0"):
    dev = MagicMock()
    dev.has_radio1 = has_radio1
    dev.send_shell_command_full.return_value = difficulty
    mock_get_dev.return_value = dev
    return dev


def _sent_frames(mock_send_raw):
    return [c[0][0] for c in mock_send_raw.call_args_list]


# ==============================================================================
# flatsat tc
# ==============================================================================

@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_sends_frame_for_apid(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 14, "response": "OK"}

    result = CliRunner().invoke(cli, ["tc", "0x04", "0164"])

    assert result.exit_code == 0
    assert "Sent APID 0x004" in result.output
    assert len(_sent_frames(mock_send_raw)) == 1

    frame = _sent_frames(mock_send_raw)[0]
    pkt = parse_frame(frame)
    assert pkt.apid == 0x04
    assert pkt.pkt_type == 1
    assert pkt.crc_valid
    assert frame[10:12] == b"\x01\x64"  # payload survives untouched


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_uses_current_time_as_default_timestamp(mock_get_dev, mock_send_raw):
    """The firmware uses the MET timestamp as the SDLS AES IV, so 0 would break it."""
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 14, "response": "OK"}

    result = CliRunner().invoke(cli, ["tc", "0x04", "0164"])

    assert result.exit_code == 0
    ts = struct.unpack(">I", _sent_frames(mock_send_raw)[0][6:10])[0]
    assert ts > 1_600_000_000, "timestamp must default to now, not 0"


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_honours_explicit_timestamp_and_seq(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 14, "response": "OK"}

    result = CliRunner().invoke(cli, ["tc", "0x04", "0164", "--timestamp", "12345", "--seq", "77"])

    assert result.exit_code == 0
    frame = _sent_frames(mock_send_raw)[0]
    assert struct.unpack(">I", frame[6:10])[0] == 12345
    assert parse_frame(frame).seq_count == 77


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_text_payload(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 20, "response": "OK"}

    result = CliRunner().invoke(cli, ["tc", "0x20", "--text", "PING"])

    assert result.exit_code == 0
    assert _sent_frames(mock_send_raw)[0][10:14] == b"PING"


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_protect_applies_sdls(mock_get_dev, mock_send_raw):

    _mock_board(mock_get_dev, difficulty="difficulty: 2")
    mock_send_raw.return_value = {"status": "sent", "bytes": 40, "response": "OK"}

    result = CliRunner().invoke(cli, ["tc", "0x01", "1000", "--protect"])

    assert result.exit_code == 0
    assert "SDLS level 2" in result.output
    sent = _sent_frames(mock_send_raw)[0]
    assert parse_frame(sent).crc_valid
    # The protected body differs from the plaintext payload.
    assert sent[10:12] != b"\x10\x00"


@patch("time.sleep", return_value=None)
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_repeat_and_delay(mock_get_dev, mock_send_raw, mock_sleep):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 14, "response": "OK"}

    result = CliRunner().invoke(cli, ["tc", "0x04", "0164", "--repeat", "3", "--delay", "0.5"])

    assert result.exit_code == 0
    assert mock_send_raw.call_count == 3
    mock_sleep.assert_called_with(0.5)


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_rejects_bad_hex(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    result = CliRunner().invoke(cli, ["tc", "0x04", "ZZZZ"])
    assert result.exit_code == 1
    assert "Invalid hex string" in result.output
    mock_send_raw.assert_not_called()


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_rejects_empty_payload(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    result = CliRunner().invoke(cli, ["tc", "0x04"])
    assert result.exit_code == 1
    assert "Empty payload" in result.output
    mock_send_raw.assert_not_called()


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_apid_range_enforced(mock_get_dev, mock_send_raw):
    result = CliRunner().invoke(cli, ["tc", "9999", "00"])
    assert result.exit_code == 2


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_tc_exit_nonzero_when_transmit_fails(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "error", "error": "Radio timeout"}

    result = CliRunner().invoke(cli, ["tc", "0x04", "0164"])

    assert result.exit_code == 1
    assert "Radio timeout" in result.output


# ==============================================================================
# flatsat attack — scenario payloads
# ==============================================================================

@patch("time.sleep", return_value=None)
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_cmd_injection_payload(mock_get_dev, mock_send_raw, mock_sleep):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 14, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "cmd-injection", "--yes"])

    assert result.exit_code == 0
    frame = _sent_frames(mock_send_raw)[0]
    assert parse_frame(frame).apid == APID_TC_SET_THRUSTER == 0x04
    assert frame[10:12] == b"\x01\x64"


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_resetc_payload(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 18, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "resetc", "--yes"])

    assert result.exit_code == 0
    frame = _sent_frames(mock_send_raw)[0]
    assert parse_frame(frame).apid == APID_TC_RESETC == 0x02
    assert frame[10:16] == b"RESETC"


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_fuzz_crash_payload(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 16, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "fuzz-crash", "--yes"])

    assert result.exit_code == 0
    frame = _sent_frames(mock_send_raw)[0]
    assert parse_frame(frame).apid == APID_TC_BROADCAST == 0x06
    assert frame[10:14] == b"\xFF\x00\xFF\xFF"


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_replay_tc_payload(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 14, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "replay-tc", "--yes"])

    assert result.exit_code == 0
    frame = _sent_frames(mock_send_raw)[0]
    assert parse_frame(frame).apid == APID_TC_REPLAY == 0x01
    assert frame[10:12] == b"\x10\x00"


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_gs_auth_uses_static_xor_key(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 30, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "gs-auth", "--yes"])

    assert result.exit_code == 0
    frame = _sent_frames(mock_send_raw)[0]
    assert parse_frame(frame).apid == APID_TC_GS_AUTH_XOR == 0x12

    expected = bytes(b ^ XOR_KEY[i % 6] for i, b in enumerate(b"AUTH_ADMIN_OVERRIDE"))
    assert frame[10:10 + len(expected)] == expected


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_mem_overflow_payload(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 76, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "mem-overflow", "--yes", "--size", "64"])

    assert result.exit_code == 0
    frame = _sent_frames(mock_send_raw)[0]
    assert parse_frame(frame).apid == APID_TC_DIAG_MEM == 0x31
    assert frame[10:74] == b"A" * 64


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_mem_overflow_requires_oversized_payload(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    result = CliRunner().invoke(cli, ["attack", "mem-overflow", "--yes", "--size", "16"])
    assert result.exit_code == 1
    assert "greater than 32" in result.output
    mock_send_raw.assert_not_called()


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_gps_spoof_sends_nmea(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 40, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "gps-spoof", "--yes", "--nmea", "$GPGGA,test*00"])

    assert result.exit_code == 0
    assert "$GPGGA,test*00" in result.output
    frame = _sent_frames(mock_send_raw)[0]
    assert frame[10:22] == b"$GPGGA,test*"


@patch("time.sleep", return_value=None)
@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_apid_enum_scans_range(mock_get_dev, mock_send_raw, mock_sleep):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 13, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "apid-enum", "--yes", "--high", "5"])

    assert result.exit_code == 0
    frames = _sent_frames(mock_send_raw)
    assert len(frames) == 6
    assert [parse_frame(f).apid for f in frames] == [0, 1, 2, 3, 4, 5]
    assert frames[0][0:2] == struct.pack(">H", 0x1800 | APID_RECON_ENUM)


# ==============================================================================
# attack — safety gates
# ==============================================================================

@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_requires_confirmation(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    result = CliRunner().invoke(cli, ["attack", "resetc"], input="n\n")
    assert result.exit_code == 1
    assert "Aborted by user" in result.output
    mock_send_raw.assert_not_called()


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_confirmation_accepts(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "sent", "bytes": 18, "response": "OK"}
    result = CliRunner().invoke(cli, ["attack", "resetc"], input="y\n")
    assert result.exit_code == 0
    assert mock_send_raw.call_count == 1


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_blocked_without_uplink_radio(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev, has_radio1=False)
    result = CliRunner().invoke(cli, ["attack", "resetc", "--yes"])
    assert result.exit_code == 1
    assert "no uplink radio" in result.output
    mock_send_raw.assert_not_called()


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_replay_tc_rejects_bad_hex(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    result = CliRunner().invoke(cli, ["attack", "replay-tc", "--yes", "--payload", "ZZ"])
    assert result.exit_code == 1
    assert "Invalid hex payload" in result.output
    mock_send_raw.assert_not_called()


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_exit_nonzero_when_transmit_fails(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev)
    mock_send_raw.return_value = {"status": "error", "error": "Radio timeout"}
    result = CliRunner().invoke(cli, ["attack", "resetc", "--yes"])
    assert result.exit_code == 1
    assert "Radio timeout" in result.output


# ==============================================================================
# attack — eavesdrop is read-only
# ==============================================================================

@patch("modules.core.session.get_device_or_exit")
def test_attack_eavesdrop_only_listens(mock_get_dev):
    from modules.core.ccsds import build_tm

    dev = _mock_board(mock_get_dev)
    frame_hex = build_tm(0x001, b"\x01").hex().upper()
    dev.read_line_from_radio.return_value = f"RX: {frame_hex} | RSSI: -40"

    with patch("modules.core.radio_bridge.RadioBridge.send_raw") as mock_send_raw:
        result = CliRunner().invoke(cli, ["attack", "eavesdrop", "-t", "0.2"])

    assert result.exit_code == 0
    assert "Captured and decrypted" in result.output
    mock_send_raw.assert_not_called()


@patch("modules.core.session.get_device_or_exit")
def test_attack_eavesdrop_exits_nonzero_when_silent(mock_get_dev):
    dev = _mock_board(mock_get_dev)
    dev.read_line_from_radio.return_value = None
    result = CliRunner().invoke(cli, ["attack", "eavesdrop", "-t", "0.1"])
    assert result.exit_code == 1
    assert "No CCSDS frames captured" in result.output


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_honours_difficulty_override_and_sdls_protects(mock_get_dev, mock_send_raw):
    _mock_board(mock_get_dev, difficulty="difficulty: 0")
    mock_send_raw.return_value = {"status": "sent", "bytes": 14, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "cmd-injection", "--power", "50", "--difficulty", "2", "--yes"])

    assert result.exit_code == 0
    assert mock_send_raw.call_count == 1
    frame = _sent_frames(mock_send_raw)[0]
    # Attack frames follow flat-sat-fw-interno Attacks/ pwnsat_packets.py (unencrypted payload evaluated directly by attacks.c)
    assert frame[10:12] == bytes([0x01, 50])



