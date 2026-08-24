import pytest
import struct

from core.ccsds import build_tc, sdls_protect_frame, ccsds_crc16, parse_frame
from core.constants import APID_TC_COMMAND, TC_OP_SET_NOMINAL
from core.radio_bridge import RadioBridge
from core.state import GroundStationState


def test_sdls_protect_frame_crc_recalculated():
    """Verify that sdls_protect_frame recalculates the CRC over ciphertext for diff 2 & 3."""
    # Build a plain telecommand frame (APID 0x020, opcode TC_OP_SET_NOMINAL=0x02)
    plain_frame = build_tc(APID_TC_COMMAND, bytes([TC_OP_SET_NOMINAL]), seq_count=1, timestamp=1600000000)

    # Difficulty 0 and 1: plaintext, CRC unchanged
    f0 = sdls_protect_frame(plain_frame, 0)
    assert f0 == plain_frame
    
    f1 = sdls_protect_frame(plain_frame, 1)
    assert f1 == plain_frame

    # Difficulty 2: XOR encryption
    f2 = sdls_protect_frame(plain_frame, 2)
    assert f2 != plain_frame
    # Check that payload bytes were transformed
    assert f2[10:11] != plain_frame[10:11]
    # Check that CRC over the ciphertext frame matches the CRC trailer in f2
    crc_computed_f2 = ccsds_crc16(f2[:-2])
    crc_trailer_f2 = struct.unpack(">H", f2[-2:])[0]
    assert crc_computed_f2 == crc_trailer_f2

    # Difficulty 3: AES-CTR encryption
    f3 = sdls_protect_frame(plain_frame, 3)
    assert f3 != plain_frame
    assert f3[10:11] != plain_frame[10:11]
    crc_computed_f3 = ccsds_crc16(f3[:-2])
    crc_trailer_f3 = struct.unpack(">H", f3[-2:])[0]
    assert crc_computed_f3 == crc_trailer_f3


class MockCatSnifferDevice:
    """Mock single-radio CatSniffer board (only radio0 and shell ports exist)."""
    def __init__(self):
        self.has_radio1 = False
        self.shell_commands = []
        self.tx_calls = []

    def send_shell_command_full(self, cmd, timeout=2.0):
        self.shell_commands.append(cmd)
        if cmd == "mode":
            return "mode: ground_station"
        if cmd == "status":
            return "Radio0: LoRa  mode=stream"
        return "OK"

    def send_shell_command(self, cmd, timeout=2.0):
        return self.send_shell_command_full(cmd, timeout)

    def reset_radio_input_buffers(self):
        pass

    def send_radio_tx(self, radio_idx, data):
        self.tx_calls.append((radio_idx, data))
        return "TX Success" if radio_idx == 0 else None

    def send_radio_raw(self, radio_idx, data):
        return False


class MockDualRadioDevice:
    """Mock dual-radio FlatSat board (has both radio0 and radio1)."""
    def __init__(self):
        self.has_radio1 = True
        self.shell_commands = []
        self.tx_calls = []

    def send_shell_command_full(self, cmd, timeout=2.0):
        self.shell_commands.append(cmd)
        if cmd == "mode":
            return "mode: ground_station"
        if cmd == "status":
            return "Radio0: LoRa  mode=stream\nRadio1: LoRa  mode=command"
        return "OK"

    def send_shell_command(self, cmd, timeout=2.0):
        return self.send_shell_command_full(cmd, timeout)

    def reset_radio_input_buffers(self):
        pass

    def send_radio_tx(self, radio_idx, data):
        self.tx_calls.append((radio_idx, data))
        return "TX Success" if radio_idx == 1 else None

    def send_radio_raw(self, radio_idx, data):
        return False


def test_radio_bridge_catsniffer_uses_radio0():
    """Verify RadioBridge uses Radio 0 in single-radio mode when has_radio1 is False."""
    dev = MockCatSnifferDevice()
    gs_state = GroundStationState()
    gs_state.set_hardware(dev)
    assert gs_state.active_radio == 0

    bridge = RadioBridge(gs_state)
    tc_frame = build_tc(APID_TC_COMMAND, bytes([TC_OP_SET_NOMINAL]))
    result = bridge.send_raw(tc_frame)

    assert result["status"] == "sent"
    assert result["response"] == "TX Success"
    assert len(dev.tx_calls) == 1
    assert dev.tx_calls[0][0] == 0
    assert "radio0" in dev.shell_commands
    assert "lora_mode R0 command" in dev.shell_commands
    assert "lora_mode R0 stream" in dev.shell_commands


def test_radio_bridge_dual_flatsat_uses_radio1_command_mode():
    """Verify RadioBridge ensures Radio 1 command mode on dual-radio FlatSat ground station."""
    dev = MockDualRadioDevice()
    gs_state = GroundStationState()
    gs_state.set_hardware(dev)
    assert gs_state.active_radio == 2

    bridge = RadioBridge(gs_state)
    tc_frame = build_tc(APID_TC_COMMAND, bytes([TC_OP_SET_NOMINAL]))
    result = bridge.send_raw(tc_frame)

    assert result["status"] == "sent"
    assert result["response"] == "TX Success"
    assert len(dev.tx_calls) == 1
    assert dev.tx_calls[0][0] == 1
    assert "radio1" in dev.shell_commands
    assert "lora_mode R1 command" in dev.shell_commands


def test_detect_local_role_catsniffer():
    """Verify _detect_local_role detects ground station role for CatSniffer."""
    from cli.commands.flight import _detect_local_role
    dev = MockCatSnifferDevice()
    role = _detect_local_role(dev)
    assert role == "ground_station"
