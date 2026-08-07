#!/usr/bin/env python3
"""
CCSDS-Inspired SPP Frame Builder/Parser for FlatSat v2.
Big-endian header format per CCSDS 133.0-B-2.
"""

import struct

# Constants
CCSDS_VERSION = 0
CCSDS_TYPE_TM = 0
CCSDS_TYPE_TC = 1
CCSDS_SEQ_STANDALONE = 3
CCSDS_HDR_SIZE = 6
CCSDS_SEC_HDR_SIZE = 4
CCSDS_CRC_SIZE = 2
CCSDS_MAX_FRAME = 237
SPACECRAFT_ID = 0x02

# Known APIDs (must match firmware ccsds_apid.h)
APIDS = {
    "TM_HEARTBEAT": 0x001,
    "TM_BME280": 0x010,
    "TM_LIS2DH": 0x011,
    "TM_POWER": 0x012,
    "TM_GPS_SIM": 0x013,
    "TM_ALL_SENSORS": 0x01F,
    "TC_COMMAND": 0x020,
    "TC_SET_FREQ": 0x021,
    "TC_SET_POWER": 0x022,
    "TC_FIRMWARE": 0x026,
    "TC_SET_DIFF": 0x027,
    "DIAG_LOG": 0x030,
    "DIAG_MEMORY": 0x031,
    "CTF_FLAG": 0x040,
    "SECRET_DEBUG": 0x539,
    "IDLE": 0x7FF,
}

# TC Opcodes (must match firmware ccsds_apid.h)
OPCODES = {
    "NOP": 0x00,
    "SET_SAFE_MODE": 0x01,
    "SET_NOMINAL": 0x02,
    "SET_DEBUG": 0x03,
    "PING": 0x10,
    "READ_SENSOR": 0x20,
    "SET_TM_RATE": 0x30,
    "OVERRIDE_SENSOR": 0x40,
    "READ_FLAG": 0x42,
    "SET_CALLSIGN": 0x50,
    "STORE_CMD": 0x60,
    "TABLE_WRITE": 0x70,
    "NEOPIXEL_RAW": 0xA0,
    "CRYPTO_ORACLE": 0xC0,
    "PRIVILEGED": 0xD0,
    "EXEC": 0xEE,
    "BACKDOOR": 0xFF,
}


def crc16_ccitt(data: bytes) -> int:
    """CRC-16-CCITT: poly=0x1021, init=0xFFFF"""
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


def build_primary_header(pkt_type: int, apid: int, seq_count: int, data_length: int) -> bytes:
    """Build 6-byte CCSDS primary header (big-endian)"""
    packet_id = (CCSDS_VERSION << 13) | (pkt_type << 12) | (1 << 11) | (apid & 0x7FF)
    seq_ctrl = (CCSDS_SEQ_STANDALONE << 14) | (seq_count & 0x3FFF)
    return struct.pack(">HHH", packet_id, seq_ctrl, data_length)


def build_secondary_header(met: int = 0) -> bytes:
    """Build 4-byte secondary header (Mission Elapsed Time)"""
    return struct.pack(">I", met)


# Auto-incrementing sequence counter (per session).
# Level 3 anti-replay rejects seq=0 and duplicate seq values.
_seq_counter = 0


def build_tc_frame(apid: int, payload: bytes, seq: int | None = None, met: int | None = None) -> bytes:
    """Build a complete CCSDS TC frame with CRC.

    seq: sequence counter. Auto-increments from 1 if not specified.
         Level 3 anti-replay rejects seq=0 and repeated values.
    """
    global _seq_counter
    import time

    if met is None:
        met = int(time.time()) & 0xFFFFFFFF
    if seq is None:
        _seq_counter = (_seq_counter + 1) & 0x3FFF
        seq = _seq_counter

    sec_hdr = build_secondary_header(met)
    data_length = len(sec_hdr) + len(payload) + CCSDS_CRC_SIZE - 1
    hdr = build_primary_header(CCSDS_TYPE_TC, apid, seq, data_length)

    frame_no_crc = hdr + sec_hdr + payload
    crc = crc16_ccitt(frame_no_crc)
    return frame_no_crc + struct.pack(">H", crc)


def build_tm_frame(apid: int, payload: bytes, seq: int = 0, met: int | None = None) -> bytes:
    """Build a complete CCSDS TM frame with CRC"""
    import time

    if met is None:
        met = int(time.time()) & 0xFFFFFFFF

    sec_hdr = build_secondary_header(met)
    data_length = len(sec_hdr) + len(payload) + CCSDS_CRC_SIZE - 1
    hdr = build_primary_header(CCSDS_TYPE_TM, apid, seq, data_length)

    frame_no_crc = hdr + sec_hdr + payload
    crc = crc16_ccitt(frame_no_crc)
    return frame_no_crc + struct.pack(">H", crc)


# ============================================================
# TM payload decoders (matches firmware telemetry.c packed structs)
# ============================================================


def decode_tm_heartbeat(payload: bytes) -> dict:
    """Decode TM_HEARTBEAT payload (13 bytes, packed little-endian)."""
    if len(payload) < 13:
        return {"error": f"short payload ({len(payload)} < 13)"}
    sc_id = payload[0]
    uptime = struct.unpack("<I", payload[1:5])[0]
    battery_mv = struct.unpack("<H", payload[5:7])[0]
    flight_mode = payload[7]
    difficulty = payload[8]
    tc_count = struct.unpack("<H", payload[9:11])[0]
    error_count = struct.unpack("<H", payload[11:13])[0]
    modes = {0: "IDLE", 1: "NOMINAL", 2: "SAFE", 3: "DEBUG"}
    return {
        "sc_id": sc_id,
        "uptime": uptime,
        "battery_mv": battery_mv,
        "flight_mode": modes.get(flight_mode, f"?{flight_mode}"),
        "difficulty": difficulty,
        "tc_count": tc_count,
        "error_count": error_count,
    }


def decode_tm_bme280(payload: bytes) -> dict:
    """Decode TM_BME280 payload (7 bytes, packed little-endian)."""
    if len(payload) < 7:
        return {"error": f"short payload ({len(payload)} < 7)"}
    temp_x100 = struct.unpack("<h", payload[0:2])[0]
    press_x10 = struct.unpack("<I", payload[2:6])[0]
    humidity = payload[6]
    return {
        "temp_c": temp_x100 / 100.0,
        "pressure_hpa": press_x10 / 1000.0,  # wire value is deci-Pascals
        "humidity_pct": humidity,
    }


def decode_tm_lis2dh(payload: bytes) -> dict:
    """Decode TM_LIS2DH payload (6 bytes, packed little-endian)."""
    if len(payload) < 6:
        return {"error": f"short payload ({len(payload)} < 6)"}
    ax, ay, az = struct.unpack("<hhh", payload[0:6])
    return {"accel_x_mg": ax, "accel_y_mg": ay, "accel_z_mg": az}


def decode_tm_power(payload: bytes) -> dict:
    """Decode TM_POWER payload (6 bytes, packed little-endian)."""
    if len(payload) < 6:
        return {"error": f"short payload ({len(payload)} < 6)"}
    bat, sol, cur = struct.unpack("<HHh", payload[0:6])
    return {"battery_mv": bat, "solar_mv": sol, "current_ma": cur}


def decode_tm_gps_sim(payload: bytes) -> dict:
    """Decode TM_GPS_SIM payload (12 bytes, packed little-endian)."""
    if len(payload) < 12:
        return {"error": f"short payload ({len(payload)} < 12)"}
    lat, lon, alt = struct.unpack("<iii", payload[0:12])
    return {"lat": lat / 1e7, "lon": lon / 1e7, "alt_m": alt / 1000.0}


TM_DECODERS = {
    APIDS["TM_HEARTBEAT"]: ("TM_HEARTBEAT", decode_tm_heartbeat),
    APIDS["TM_BME280"]: ("TM_BME280", decode_tm_bme280),
    APIDS["TM_LIS2DH"]: ("TM_LIS2DH", decode_tm_lis2dh),
    APIDS["TM_POWER"]: ("TM_POWER", decode_tm_power),
    APIDS["TM_GPS_SIM"]: ("TM_GPS_SIM", decode_tm_gps_sim),
}


def decode_tm(frame: bytes) -> dict:
    """Parse a TM frame, decrypt if needed (auto-detect), and decode payload."""
    p = parse_frame(frame)
    if not p.get("crc_valid"):
        # Try XOR then CTR
        for name, fn in [("XOR", sdls_xor_payload), ("CTR", sdls_ctr_payload)]:
            try:
                dec = fn(frame)
                pd = parse_frame(dec)
                if pd.get("crc_valid"):
                    p = pd
                    p["sdls"] = name
                    break
            except Exception:
                pass
        else:
            p["sdls"] = "FAIL"
    else:
        p["sdls"] = "PLAIN"

    apid = p.get("apid", 0)
    if apid in TM_DECODERS and "payload" in p:
        name, decoder = TM_DECODERS[apid]
        p["decoded"] = decoder(p["payload"])
    return p


# ============================================================
# SDLS encryption (matches firmware ccsds_sdls.c)
# ============================================================

XOR_KEY = b"PWNSAT"
AES_KEY = b"PWNSAT_K3Y_2026!"


def sdls_xor_payload(frame: bytes) -> bytes:
    """XOR-encrypt/decrypt the payload region of a CCSDS frame (Level 2).
    Symmetric — same function for encrypt and decrypt."""
    frame = bytearray(frame)
    payload_start = CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE
    payload_end = len(frame) - CCSDS_CRC_SIZE
    for i in range(payload_start, payload_end):
        frame[i] ^= XOR_KEY[(i - payload_start) % len(XOR_KEY)]
    return bytes(frame)


def sdls_ctr_payload(frame: bytes) -> bytes:
    """AES-128-CTR encrypt/decrypt the payload region of a CCSDS frame (Level 3).
    IV derived from secondary header MET (bytes 6-9), zero-padded to 16."""
    try:
        from Crypto.Cipher import AES
    except ImportError:
        from Cryptodome.Cipher import AES

    frame = bytearray(frame)
    payload_start = CCSDS_HDR_SIZE + CCSDS_SEC_HDR_SIZE
    payload_end = len(frame) - CCSDS_CRC_SIZE
    payload = bytes(frame[payload_start:payload_end])

    iv = bytes(frame[CCSDS_HDR_SIZE : CCSDS_HDR_SIZE + 4]) + b"\x00" * 12
    cipher = AES.new(AES_KEY, AES.MODE_CTR, nonce=b"", initial_value=iv)
    encrypted = cipher.encrypt(payload)

    frame[payload_start:payload_end] = encrypted
    return bytes(frame)


def parse_frame(data: bytes) -> dict:
    """Parse a CCSDS frame into its components"""
    if len(data) < CCSDS_HDR_SIZE:
        return {"error": "Frame too short"}

    packet_id, seq_ctrl, data_length = struct.unpack(">HHH", data[:6])

    result = {
        "version": (packet_id >> 13) & 0x07,
        "type": "TC" if (packet_id >> 12) & 0x01 else "TM",
        "sec_hdr": (packet_id >> 11) & 0x01,
        "apid": packet_id & 0x07FF,
        "seq_flags": (seq_ctrl >> 14) & 0x03,
        "seq_count": seq_ctrl & 0x3FFF,
        "data_len": data_length + 1,
    }

    # Secondary header
    if result["sec_hdr"] and len(data) >= 10:
        result["met"] = struct.unpack(">I", data[6:10])[0]

    # Payload
    payload_start = CCSDS_HDR_SIZE + (CCSDS_SEC_HDR_SIZE if result["sec_hdr"] else 0)
    payload_end = len(data) - CCSDS_CRC_SIZE
    if payload_end > payload_start:
        result["payload"] = data[payload_start:payload_end]
        result["payload_hex"] = data[payload_start:payload_end].hex()

    # CRC
    if len(data) >= payload_end + 2:
        rx_crc = struct.unpack(">H", data[payload_end : payload_end + 2])[0]
        calc_crc = crc16_ccitt(data[:payload_end])
        result["crc_rx"] = f"0x{rx_crc:04X}"
        result["crc_calc"] = f"0x{calc_crc:04X}"
        result["crc_valid"] = rx_crc == calc_crc

    return result


def print_frame(data: bytes):
    """Pretty-print a parsed CCSDS frame"""
    f = parse_frame(data)
    if "error" in f:
        print(f"[!] {f['error']}")
        return

    apid_name = next((k for k, v in APIDS.items() if v == f["apid"]), "UNKNOWN")
    print(f"┌── CCSDS Frame ({len(data)} bytes) ──")
    print(f"│ Type:     {f['type']}")
    print(f"│ APID:     0x{f['apid']:03X} ({apid_name})")
    print(f"│ Seq:      {f['seq_count']}")
    print(f"│ Data Len: {f['data_len']}")
    if "met" in f:
        print(f"│ MET:      {f['met']} sec")
    if "payload_hex" in f:
        print(f"│ Payload:  {f['payload_hex']}")
    if "crc_valid" in f:
        print(f"│ CRC:      {f['crc_rx']} ({'OK' if f['crc_valid'] else 'FAIL'})")
    print("└──────────────────────────")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  ccsds_tools.py parse <hex>          Parse a frame")
        print("  ccsds_tools.py build-tc <apid> <payload_hex>  Build TC")
        print("  ccsds_tools.py ping                 Build PING TC")
        print("  ccsds_tools.py nop                  Build NOP TC")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "parse":
        data = bytes.fromhex(sys.argv[2])
        print_frame(data)

    elif cmd == "build-tc":
        apid = int(sys.argv[2], 0)
        payload = bytes.fromhex(sys.argv[3]) if len(sys.argv) > 3 else b""
        frame = build_tc_frame(apid, payload)
        print(f"Frame: {frame.hex()}")
        print_frame(frame)

    elif cmd == "ping":
        frame = build_tc_frame(APIDS["TC_COMMAND"], bytes([OPCODES["PING"]]))
        print(f"PING frame: {frame.hex()}")

    elif cmd == "nop":
        frame = build_tc_frame(APIDS["TC_COMMAND"], bytes([OPCODES["NOP"]]))
        print(f"NOP frame: {frame.hex()}")
