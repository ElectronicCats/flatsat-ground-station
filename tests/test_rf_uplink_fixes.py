"""Regression tests for the RF uplink that carried CTF attacks.

Three defects made `flatsat attack ...` report success while nothing reached the
target board:

1. ``RadioBridge.send_raw`` configured frequency and mode on the uplink radio
   but never the LoRa *sync word*. Radio 1 ships on the private sync word
   (0x12) while the satellite listens on the public one (0x34), so the SX126x
   never demodulated a single telecommand — while still answering
   ``TX Result: 0 (Success)``, which only means the packet was queued.
2. The SDLS level used to build frames came from the *local* board, which with
   two FlatSats connected is the ground station, not the satellite being
   attacked. Now sniffed off the target's own heartbeat.
3. The CTF attack frames are deliberately plaintext (the firmware dispatches
   them from the plaintext APID header), so they must NOT be SDLS-protected —
   and in particular ``gs-auth`` pre-XORs its payload for the firmware to XOR
   a second time. Guarded here so a well-meaning "encrypt everything" change
   cannot silently break that scenario again.
"""

import struct
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from modules.core.ccsds import build_tm, parse_frame
from modules.core.cli import _attack_frame, _resolve_difficulty, cli
from modules.core.constants import (
    APID_TC_RESETC,
    APID_TC_SET_THRUSTER,
    LORA_SYNCWORD_TX,
)
from modules.core.radio_bridge import RadioBridge
from modules.core.state import GroundStationState

SYNCWORD_PRIVATE_RESPONSE = (
    "LoRa Configuration [Radio 1]:\n"
    "  Frequency: 915000000 Hz\n"
    "  Sync Word: Private (0x12)\n"
)


def _bridge_device(syncword_response=SYNCWORD_PRIVATE_RESPONSE):
    dev = MagicMock()
    dev.has_radio1 = True
    dev.send_shell_command_full.return_value = syncword_response
    dev.send_radio_tx.return_value = "TX Result: 0 (Success)"
    state = GroundStationState()
    state.set_hardware(dev)
    state.device = dev
    return dev, RadioBridge(state)


def _shell_calls(dev):
    return [c[0][0] for c in dev.send_shell_command_full.call_args_list]


# ==============================================================================
# Sync word
# ==============================================================================


def test_tx_sets_sync_word_before_transmitting():
    """The uplink radio must be on the same sync word the target listens on."""
    dev, bridge = _bridge_device()
    bridge.send_raw(b"\xaa\xbb")

    calls = _shell_calls(dev)
    sync = calls.index(f"lora_syncword R1 {LORA_SYNCWORD_TX}")
    # It has to be applied before the packet leaves the board.
    assert calls.index("lora_apply R1") > sync
    assert dev.send_radio_tx.called


def test_tx_sets_uplink_frequency_and_command_mode():
    dev, bridge = _bridge_device()
    bridge.send_raw(b"\xaa\xbb")

    calls = _shell_calls(dev)
    assert "lora_freq R1 916000000" in calls
    assert "lora_mode R1 command" in calls


def test_tx_restores_previous_sync_word_afterwards():
    dev, bridge = _bridge_device()
    bridge.send_raw(b"\xaa\xbb")

    calls = _shell_calls(dev)
    # Operator's setting is put back, so we do not leave the radio reconfigured.
    assert calls.index("lora_syncword R1 private") > calls.index("lora_apply R1")


def test_result_reports_the_sync_word_used():
    dev, bridge = _bridge_device()
    result = bridge.send_raw(b"\xaa\xbb")

    assert result["status"] == "sent"
    assert result["syncword"] == LORA_SYNCWORD_TX
    assert result["radio"] == 1


def test_failed_revert_does_not_raise_or_mask_a_successful_send():
    """A revert failure must not turn a good transmit into a crash."""
    dev, bridge = _bridge_device()
    dev.send_radio_tx.return_value = "TX Result: 0 (Success)"

    def explode(*_args, **_kwargs):
        raise RuntimeError("radio went away mid-revert")

    bridge._restore_rx = explode

    result = bridge.send_raw(b"\xaa\xbb")

    assert result["status"] == "sent"
    assert bridge._state.tx_in_progress is False


# ==============================================================================
# Attack frames stay plaintext
# ==============================================================================


def test_attack_frame_payload_is_not_sdls_protected():
    """CTF attacks dispatch on the plaintext APID header; encrypting breaks gs-auth."""
    frame = _attack_frame(APID_TC_SET_THRUSTER, b"\x01\x64", seq_count=1)

    assert frame[10:12] == b"\x01\x64"
    assert parse_frame(frame).crc_valid


def test_attack_frame_carries_the_requested_apid_and_seq():
    frame = _attack_frame(APID_TC_RESETC, b"RESETC", seq_count=9)
    pkt = parse_frame(frame)

    assert pkt.apid == APID_TC_RESETC
    assert pkt.seq_count == 9
    assert struct.unpack(">I", frame[6:10])[0] > 1_600_000_000


# ==============================================================================
# Difficulty comes from the target, not the local board
# ==============================================================================


def _heartbeat_line(difficulty):
    """A downlink line carrying a heartbeat encrypted at `difficulty`.

    detect_tm_difficulty needs the 13-byte heartbeat payload, hence the padding
    past the 9 bytes of sc_id/uptime/battery/flight_mode/difficulty.
    """
    from modules.core.ccsds import sdls_protect_frame

    payload = struct.pack("<BIHBB", 0x02, 1_700_000_000, 3300, 2, difficulty).ljust(13, b"\x00")
    frame = build_tm(0x001, payload, seq_count=1, timestamp=1_700_000_000)
    if difficulty >= 2:
        frame = sdls_protect_frame(frame, difficulty)
    return f"RX: {frame.hex()} | RSSI: -57 | SNR: 12"


def test_difficulty_sniffed_from_target_heartbeat_overrides_local_board():
    dev = MagicMock()
    # Local board is at level 1, the satellite actually being attacked is at 2.
    dev.send_shell_command_full.return_value = "difficulty\ndifficulty: 1 (normal)"
    dev.read_line_from_radio.side_effect = [None, _heartbeat_line(2)]

    level, source = _resolve_difficulty(dev, None)

    assert level == 2
    assert source == "sniffed"


def test_explicit_difficulty_flag_skips_the_sniff():
    dev = MagicMock()
    level, source = _resolve_difficulty(dev, 3)

    assert level == 3
    assert not dev.read_line_from_radio.called


def test_falls_back_to_local_board_when_nothing_is_sniffed():
    dev = MagicMock()
    dev.send_shell_command_full.return_value = "difficulty\ndifficulty: 2 (medium)"
    dev.read_line_from_radio.return_value = None

    level, source = _resolve_difficulty(dev, None, timeout=0.05)

    assert level == 2
    assert source == "local board"


# ==============================================================================
# CLI surface
# ==============================================================================


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_group_accepts_device_option(mock_get_dev, mock_send_raw):
    """`flatsat attack -d 0 resetc` must work, not just `flatsat -d 0 attack ...`."""
    mock_get_dev.return_value = MagicMock()
    mock_send_raw.return_value = {"status": "sent", "bytes": 12, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "-d", "0", "resetc", "--yes"])

    assert result.exit_code == 0, result.output
    mock_get_dev.assert_called_once_with(device="0", port=None)


@patch("modules.core.radio_bridge.RadioBridge.send_raw")
@patch("modules.core.session.get_device_or_exit")
def test_attack_reports_expected_target_led_colour(mock_get_dev, mock_send_raw):
    """The NeoPixel is the only real proof the frame landed; tell the user what to look for."""
    mock_get_dev.return_value = MagicMock()
    mock_send_raw.return_value = {"status": "sent", "bytes": 12, "response": "OK"}

    result = CliRunner().invoke(cli, ["attack", "-d", "0", "cmd-injection", "--yes"])

    assert result.exit_code == 0, result.output
    assert "yellow" in result.output
    assert "50,50,0" in result.output
