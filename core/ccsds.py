"""CCSDS Space Packet Protocol encoder/decoder.

Matches firmware implementation in flatsat/src/ccsds/ccsds_spp.c.
Big-endian headers per CCSDS 133.0-B-2.
"""

import struct
from dataclasses import dataclass

from core.constants import (
    CCSDS_CRC_SIZE,
    CCSDS_HDR_SIZE,
    CCSDS_MAX_PAYLOAD,
    CCSDS_SEC_HDR_SIZE,
    CCSDS_SEQ_STANDALONE,
    CCSDS_TYPE_TC,
    CCSDS_TYPE_TM,
    CCSDS_VERSION,
)


@dataclass
class CcsdsPacket:
    pkt_type: int
    sec_hdr_flag: int
    apid: int
    seq_flags: int
    seq_count: int
    timestamp: int
    payload: bytes
    crc_valid: bool
    raw: bytes = b""


def ccsds_crc16(data: bytes) -> int:
    """CRC-16-CCITT: polynomial 0x1021, initial 0xFFFF."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc


def build_packet_id(pkt_type: int, apid: int) -> int:
    """Build 16-bit packet_id: version(3) | type(1) | sec_hdr(1) | apid(11)."""
    return ((CCSDS_VERSION & 0x7) << 13) | ((pkt_type & 0x1) << 12) | (1 << 11) | (apid & 0x7FF)


def parse_packet_id(packet_id: int) -> tuple[int, int, int]:
    """Parse packet_id into (type, sec_hdr_flag, apid)."""
    pkt_type = (packet_id >> 12) & 0x1
    sec_hdr = (packet_id >> 11) & 0x1
    apid = packet_id & 0x7FF
    return pkt_type, sec_hdr, apid


def build_seq_ctrl(seq_count: int, seq_flags: int = CCSDS_SEQ_STANDALONE) -> int:
    """Build 16-bit sequence control: flags(2) | count(14)."""
    return ((seq_flags & 0x3) << 14) | (seq_count & 0x3FFF)


def parse_seq_ctrl(seq_ctrl: int) -> tuple[int, int]:
    """Parse sequence control into (flags, count)."""
    flags = (seq_ctrl >> 14) & 0x3
    count = seq_ctrl & 0x3FFF
    return flags, count


def _build_frame(pkt_type: int, apid: int, payload: bytes, seq_count: int, timestamp: int) -> bytes:
    """Build a complete CCSDS frame with primary header, secondary header, payload, and CRC."""
    if len(payload) > CCSDS_MAX_PAYLOAD:
        raise ValueError(f"payload too large: {len(payload)} > {CCSDS_MAX_PAYLOAD}")

    packet_id = build_packet_id(pkt_type, apid)
    seq_ctrl = build_seq_ctrl(seq_count)
    data_length = CCSDS_SEC_HDR_SIZE + len(payload) + CCSDS_CRC_SIZE - 1

    hdr = struct.pack(">HHH", packet_id, seq_ctrl, data_length)
    sec_hdr = struct.pack(">I", timestamp & 0xFFFFFFFF)

    frame_no_crc = hdr + sec_hdr + payload
    crc = ccsds_crc16(frame_no_crc)
    return frame_no_crc + struct.pack(">H", crc)


def build_tm(apid: int, payload: bytes, seq_count: int = 0, timestamp: int = 0) -> bytes:
    """Build a telemetry (TM) frame."""
    return _build_frame(CCSDS_TYPE_TM, apid, payload, seq_count, timestamp)


def build_tc(apid: int, payload: bytes, seq_count: int = 0, timestamp: int = 0) -> bytes:
    """Build a telecommand (TC) frame."""
    return _build_frame(CCSDS_TYPE_TC, apid, payload, seq_count, timestamp)


def parse_frame(raw: bytes) -> CcsdsPacket | None:
    """Parse a raw CCSDS frame. Returns None if too short or truncated."""
    min_size = CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE + CCSDS_CRC_SIZE
    if len(raw) < min_size:
        return None

    packet_id, seq_ctrl, data_length = struct.unpack(">HHH", raw[:6])
    pkt_type, sec_hdr_flag, apid = parse_packet_id(packet_id)
    seq_flags, seq_count = parse_seq_ctrl(seq_ctrl)

    # Use data_length to determine actual frame boundary
    total_length = CCSDS_HDR_SIZE + data_length + 1
    if len(raw) < total_length:
        return None

    timestamp = struct.unpack(">I", raw[6:10])[0]

    payload_end = total_length - CCSDS_CRC_SIZE
    payload = raw[10:payload_end]

    expected_crc = ccsds_crc16(raw[:payload_end])
    actual_crc = struct.unpack(">H", raw[payload_end:total_length])[0]

    return CcsdsPacket(
        pkt_type=pkt_type,
        sec_hdr_flag=sec_hdr_flag,
        apid=apid,
        seq_flags=seq_flags,
        seq_count=seq_count,
        timestamp=timestamp,
        payload=payload,
        crc_valid=(expected_crc == actual_crc),
        raw=raw[:total_length],
    )
