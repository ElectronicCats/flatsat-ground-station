from core.ccsds import parse_frame
from core.constants import (
    APID_TC_COMMAND,
    CCSDS_TYPE_TC,
    TC_OP_PING,
    TC_OP_PRIVILEGED,
    TC_OP_READ_FLAG,
)
from core.telecommand import (
    build_command_tc,
    build_privileged_tc,
    build_frequency_tc,
    build_power_tc,
    xor_decrypt,
    xor_encrypt,
)


def test_build_command_tc_ping():
    frame = build_command_tc(TC_OP_PING)
    pkt = parse_frame(frame)
    assert pkt.pkt_type == CCSDS_TYPE_TC
    assert pkt.apid == APID_TC_COMMAND
    assert pkt.payload[0] == TC_OP_PING
    assert pkt.crc_valid


def test_build_command_tc_with_data():
    data = b"\x01\x02\x03\x04"
    frame = build_command_tc(TC_OP_PING, data=data)
    pkt = parse_frame(frame)
    assert pkt.payload == bytes([TC_OP_PING]) + data


def test_build_privileged_tc():
    frame = build_privileged_tc(TC_OP_READ_FLAG)
    pkt = parse_frame(frame)
    assert pkt.apid == APID_TC_COMMAND
    assert pkt.payload[0] == TC_OP_PRIVILEGED
    assert len(pkt.payload) == 17


def test_xor_roundtrip():
    original = b"Hello, World!"
    encrypted = xor_encrypt(original)
    decrypted = xor_decrypt(encrypted)
    assert decrypted == original


def test_xor_encrypt_known():
    data = b"PWNSAT"
    encrypted = xor_encrypt(data)
    assert encrypted == b"\x00" * 6


def test_build_frequency_tc():
    import struct
    from core.constants import APID_TC_SET_FREQ
    frame = build_frequency_tc(radio_idx=1, frequency_hz=916000000)
    pkt = parse_frame(frame)
    assert pkt.pkt_type == CCSDS_TYPE_TC
    assert pkt.apid == APID_TC_SET_FREQ
    radio_idx, freq = struct.unpack("<BI", pkt.payload)
    assert radio_idx == 1
    assert freq == 916000000


def test_build_power_tc():
    import struct
    from core.constants import APID_TC_SET_POWER
    frame = build_power_tc(radio_idx=0, power_dbm=14)
    pkt = parse_frame(frame)
    assert pkt.pkt_type == CCSDS_TYPE_TC
    assert pkt.apid == APID_TC_SET_POWER
    radio_idx, power = struct.unpack("<Bb", pkt.payload)
    assert radio_idx == 0
    assert power == 14

