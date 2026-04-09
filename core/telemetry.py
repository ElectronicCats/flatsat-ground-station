"""Telemetry decoder and mock generator.

Decodes TM payloads by APID, matching firmware struct formats.
Generates synthetic telemetry for mock mode.
"""

import random
import struct
import time

from core.ccsds import build_tm, parse_frame
from core.constants import (
    APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH,
    CCSDS_SPACECRAFT_ID,
)


def decode_heartbeat(payload: bytes) -> dict:
    sc_id, uptime, battery_mv, flight_mode, difficulty, tc_count, error_count = struct.unpack(
        ">BIHBBHH", payload[:13]
    )
    return {
        "sc_id": sc_id,
        "uptime": uptime,
        "battery_mv": battery_mv,
        "flight_mode": flight_mode,
        "difficulty": difficulty,
        "tc_count": tc_count,
        "error_count": error_count,
    }


def decode_bme280(payload: bytes) -> dict:
    temp_x100, press_x10, humidity = struct.unpack(">hIB", payload[:7])
    return {
        "temperature": temp_x100 / 100.0,
        "pressure": press_x10 / 10.0,
        "humidity": humidity,
    }


def decode_lis2dh(payload: bytes) -> dict:
    accel_x, accel_y, accel_z = struct.unpack(">hhh", payload[:6])
    return {
        "accel_x": accel_x,
        "accel_y": accel_y,
        "accel_z": accel_z,
    }


_DECODERS = {
    APID_TM_HEARTBEAT: decode_heartbeat,
    APID_TM_BME280: decode_bme280,
    APID_TM_LIS2DH: decode_lis2dh,
}


def decode_tm_payload(apid: int, payload: bytes) -> dict:
    decoder = _DECODERS.get(apid)
    if decoder:
        return decoder(payload)
    return {"raw": payload}


_mock_seq_count = 0


def generate_mock_telemetry() -> dict:
    global _mock_seq_count
    apid = random.choice([APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH])
    timestamp = int(time.time()) & 0xFFFFFFFF

    if apid == APID_TM_HEARTBEAT:
        payload = struct.pack(">BIHBBHH", CCSDS_SPACECRAFT_ID, timestamp, random.randint(3300, 4200), random.randint(0, 2), 0, random.randint(0, 500), random.randint(0, 5))
    elif apid == APID_TM_BME280:
        payload = struct.pack(">hIB", random.randint(2000, 3500), random.randint(10100, 10200), random.randint(40, 60))
    else:
        payload = struct.pack(">hhh", random.randint(-50, 50), random.randint(-50, 50), random.randint(950, 1050))

    frame = build_tm(apid, payload, seq_count=_mock_seq_count, timestamp=timestamp)
    _mock_seq_count = (_mock_seq_count + 1) & 0x3FFF

    decoded = decode_tm_payload(apid, payload)
    return {"apid": apid, "timestamp": timestamp, "frame": frame, "raw_hex": frame.hex(), "decoded": decoded}
