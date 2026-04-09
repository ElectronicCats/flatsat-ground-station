from core.ccsds import (
    build_packet_id,
    build_seq_ctrl,
    build_tc,
    build_tm,
    ccsds_crc16,
    parse_frame,
    parse_packet_id,
    parse_seq_ctrl,
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
