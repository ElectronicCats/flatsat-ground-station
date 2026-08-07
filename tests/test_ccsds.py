import struct

from core.ccsds import (
    build_packet_id,
    build_seq_ctrl,
    build_tc,
    build_tm,
    ccsds_crc16,
    detect_tm_difficulty,
    parse_frame,
    parse_packet_id,
    parse_seq_ctrl,
    sdls_protect_frame,
    sdls_unprotect_frame,
)
from core.constants import (
    APID_TC_COMMAND,
    APID_TM_BME280,
    APID_TM_HEARTBEAT,
    CCSDS_CRC_SIZE,
    CCSDS_HDR_SIZE,
    CCSDS_MAX_PAYLOAD,
    CCSDS_SEC_HDR_SIZE,
    CCSDS_SEQ_STANDALONE,
    CCSDS_SPACECRAFT_ID,
    CCSDS_TYPE_TC,
    CCSDS_TYPE_TM,
)


def test_crc16_empty():
    assert ccsds_crc16(b"") == 0xFFFF


def test_crc16_known():
    data = b"123456789"
    crc = ccsds_crc16(data)
    assert crc == 0x29B1


def test_build_packet_id_tm():
    pid = build_packet_id(CCSDS_TYPE_TM, APID_TM_HEARTBEAT)
    assert pid == 0x0801


def test_build_packet_id_tc():
    pid = build_packet_id(CCSDS_TYPE_TC, APID_TC_COMMAND)
    assert pid == 0x1820


def test_parse_packet_id():
    pkt_type, sec_hdr, apid = parse_packet_id(0x0801)
    assert pkt_type == CCSDS_TYPE_TM
    assert sec_hdr == 1
    assert apid == 0x001


def test_build_seq_ctrl():
    seq = build_seq_ctrl(42)
    assert seq == 0xC02A


def test_parse_seq_ctrl():
    flags, count = parse_seq_ctrl(0xC02A)
    assert flags == CCSDS_SEQ_STANDALONE
    assert count == 42


def test_build_tm_roundtrip():
    payload = b"\x02\x00\x00\x00\x64\x03\xe8\x01\x32\x00\x0a\x00\x00"
    frame = build_tm(APID_TM_HEARTBEAT, payload, seq_count=1, timestamp=100)
    assert len(frame) == CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE + len(payload) + CCSDS_CRC_SIZE
    pkt = parse_frame(frame)
    assert pkt.pkt_type == CCSDS_TYPE_TM
    assert pkt.apid == APID_TM_HEARTBEAT
    assert pkt.seq_count == 1
    assert pkt.timestamp == 100
    assert pkt.payload == payload
    assert pkt.crc_valid is True


def test_build_tc_roundtrip():
    payload = bytes([0x10])
    frame = build_tc(APID_TC_COMMAND, payload, seq_count=5, timestamp=200)
    pkt = parse_frame(frame)
    assert pkt.pkt_type == CCSDS_TYPE_TC
    assert pkt.apid == APID_TC_COMMAND
    assert pkt.seq_count == 5
    assert pkt.timestamp == 200
    assert pkt.payload == payload
    assert pkt.crc_valid is True


def test_parse_bad_crc():
    frame = build_tm(APID_TM_BME280, b"\x01\x02\x03", seq_count=0, timestamp=0)
    corrupted = bytearray(frame)
    corrupted[-1] ^= 0xFF
    pkt = parse_frame(bytes(corrupted))
    assert pkt.crc_valid is False


def test_parse_too_short():
    pkt = parse_frame(b"\x00\x01\x02")
    assert pkt is None


def test_max_payload():
    payload = bytes(CCSDS_MAX_PAYLOAD)
    frame = build_tm(APID_TM_HEARTBEAT, payload, seq_count=0, timestamp=0)
    pkt = parse_frame(frame)
    assert pkt.payload == payload


def test_payload_too_large():
    import pytest

    with pytest.raises(ValueError, match="payload"):
        build_tm(APID_TM_HEARTBEAT, bytes(CCSDS_MAX_PAYLOAD + 1), seq_count=0, timestamp=0)


def test_sdls_ctr_round_trip():
    """Level 3 AES-CTR: protect then unprotect returns original frame."""
    payload = bytes([0x10])  # PING opcode
    frame = build_tc(APID_TC_COMMAND, payload, seq_count=1, timestamp=12345)
    protected = sdls_protect_frame(frame, difficulty=3)
    assert protected != frame, "CTR should change the frame"
    recovered = sdls_unprotect_frame(protected, difficulty=3)
    assert recovered == frame, "CTR round-trip must recover original"


def test_sdls_ctr_different_timestamps_produce_different_ciphertext():
    """Different MET timestamps must produce different ciphertext (CTR IV varies)."""
    payload = bytes([0x10])
    frame_a = build_tc(APID_TC_COMMAND, payload, seq_count=1, timestamp=100)
    frame_b = build_tc(APID_TC_COMMAND, payload, seq_count=1, timestamp=200)
    enc_a = sdls_protect_frame(frame_a, difficulty=3)
    enc_b = sdls_protect_frame(frame_b, difficulty=3)
    # Payloads should differ because IV (from timestamp) differs
    assert enc_a[10:-2] != enc_b[10:-2]


def test_sdls_xor_still_works():
    """Level 2 XOR: protect then unprotect returns original frame."""
    payload = bytes([0x10, 0x20, 0x30])
    frame = build_tc(APID_TC_COMMAND, payload, seq_count=1, timestamp=0)
    protected = sdls_protect_frame(frame, difficulty=2)
    assert protected != frame
    recovered = sdls_unprotect_frame(protected, difficulty=2)
    assert recovered == frame


def test_sdls_plaintext_passthrough():
    """Level 0-1: no encryption applied."""
    payload = bytes([0x10])
    frame = build_tc(APID_TC_COMMAND, payload, seq_count=1, timestamp=0)
    assert sdls_protect_frame(frame, difficulty=0) == frame
    assert sdls_protect_frame(frame, difficulty=1) == frame


def _firmware_heartbeat(difficulty: int, timestamp: int = 447) -> bytes:
    """Build a heartbeat the way the firmware does: encrypt payload, then CRC.

    Mirrors main.c sat_telem_func(), where uptime and the secondary-header
    timestamp both come from the same k_uptime_get() / 1000.
    """
    payload = struct.pack("<BIHBBHH", CCSDS_SPACECRAFT_ID, timestamp, 4200, 1, difficulty, 3, 0)
    frame = build_tm(APID_TM_HEARTBEAT, payload, seq_count=0, timestamp=timestamp)
    if difficulty < 2:
        return frame
    # Encrypt-then-CRC: recompute the CRC over the ciphertext.
    protected = sdls_protect_frame(frame, difficulty)
    body = protected[: len(protected) - CCSDS_CRC_SIZE]
    return body + struct.pack(">H", ccsds_crc16(body))


def test_detect_tm_difficulty_all_levels():
    """Every firmware difficulty is recoverable from its heartbeat alone."""
    for level in (0, 1, 2, 3):
        assert detect_tm_difficulty(_firmware_heartbeat(level)) == level


def test_detect_tm_difficulty_ignores_non_heartbeat():
    """Only heartbeats carry the invariants, so other APIDs must not be guessed at."""
    frame = build_tm(APID_TM_BME280, bytes(7), seq_count=0, timestamp=447)
    assert detect_tm_difficulty(frame) is None


def test_detect_tm_difficulty_rejects_garbage():
    """A frame that satisfies no candidate must return None, not a wrong level."""
    payload = struct.pack("<BIHBBHH", 0xFF, 999999, 4200, 9, 7, 3, 0)
    frame = build_tm(APID_TM_HEARTBEAT, payload, seq_count=0, timestamp=447)
    assert detect_tm_difficulty(frame) is None
    assert detect_tm_difficulty(b"\x00\x01") is None


def test_detect_tm_difficulty_survives_encrypt_then_crc():
    """The wrong level still passes CRC, so detection must not lean on crc_valid."""
    frame = _firmware_heartbeat(3)
    assert parse_frame(frame).crc_valid, "encrypt-then-CRC frame is CRC-valid as received"
    assert detect_tm_difficulty(frame) == 3
