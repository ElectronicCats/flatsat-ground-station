#!/usr/bin/env python3
"""
pwnsat_packets.py - CCSDS Space Packet Building and CRC Validation Helper for flat-sat-fw-interno
"""
import struct
import time

def ccsds_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def build_ccsds_packet(apid: int, payload: bytes, seq_count: int = 1) -> bytes:
    # Primary Header: 6 bytes
    # Version (0), Type (1=TC), SecHdr (1), APID (11 bits)
    packet_id = 0x1800 | (apid & 0x07FF)
    seq_ctrl = 0xC000 | (seq_count & 0x3FFF)
    data_len = len(payload) + 4 + 2 - 1 # Secondary hdr (4) + payload + CRC (2) - 1

    header = struct.pack(">HHH", packet_id, seq_ctrl, data_len)
    sec_hdr = struct.pack(">I", int(time.time()))

    frame_data = header + sec_hdr + payload
    crc = ccsds_crc16(frame_data)
    return frame_data + struct.pack(">H", crc)
