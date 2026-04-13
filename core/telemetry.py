"""Telemetry decoder and mock generator.

Decodes TM payloads by APID, matching firmware struct formats.
Generates synthetic telemetry for mock mode.
"""

import random
import struct
import time

from core.ccsds import build_tm
from core.constants import (
    APID_TM_ALL_SENSORS,
    APID_TM_BME280,
    APID_TM_GPS,
    APID_TM_HEARTBEAT,
    APID_TM_LIS2DH,
    APID_TM_POWER,
    CCSDS_SPACECRAFT_ID,
)


def decode_heartbeat(payload: bytes) -> dict:
    """Decode heartbeat TM payload (APID 0x001).

    Firmware sends packed struct in native (little-endian) byte order.
    CCSDS headers are big-endian, but payloads are RP2040 native = LE.
    """
    sc_id, uptime, battery_mv, flight_mode, difficulty, tc_count, error_count = struct.unpack("<BIHBBHH", payload[:13])
    return {
        "sc_id": sc_id,
        "uptime": uptime,
        "battery_mv": battery_mv,
        "flight_mode": flight_mode,
        "flight": flight_mode_name(flight_mode),
        "difficulty": difficulty,
        "tc_count": tc_count,
        "error_count": error_count,
    }


def decode_bme280(payload: bytes) -> dict:
    """Decode BME280 TM payload (APID 0x010). Little-endian."""
    temp_x100, press_x10, humidity = struct.unpack("<hIB", payload[:7])
    return {
        "temperature": temp_x100 / 100.0,
        "pressure": press_x10 / 10.0,
        "humidity": humidity,
    }


def decode_lis2dh(payload: bytes) -> dict:
    """Decode LIS2DH accelerometer TM payload (APID 0x011). Little-endian."""
    accel_x, accel_y, accel_z = struct.unpack("<hhh", payload[:6])
    return {
        "accel_x": accel_x,
        "accel_y": accel_y,
        "accel_z": accel_z,
    }


def decode_power(payload: bytes) -> dict:
    """Decode Power TM payload (APID 0x012). Little-endian packed struct."""
    battery_mv, solar_mv, current_ma = struct.unpack("<HHh", payload[:6])
    return {
        "battery_mv": battery_mv,
        "solar_mv": solar_mv,
        "current_ma": current_ma,
    }


def decode_gps_sim(payload: bytes) -> dict:
    """Decode GPS Sim TM payload (APID 0x013). Little-endian packed struct."""
    lat_x1e7, lon_x1e7, alt_mm = struct.unpack("<iii", payload[:12])
    return {
        "latitude": lat_x1e7 / 1e7,
        "longitude": lon_x1e7 / 1e7,
        "altitude_m": alt_mm / 1000.0,
    }


def decode_all_sensors(payload: bytes) -> dict:
    """Decode All-Sensors TM payload (APID 0x01F). Little-endian packed struct."""
    temp_x100, press_x10, humidity, ax, ay, az, battery_mv = struct.unpack("<hIBhhhH", payload[:15])
    return {
        "temperature": temp_x100 / 100.0,
        "pressure": press_x10 / 10.0,
        "humidity": humidity,
        "accel_x": ax,
        "accel_y": ay,
        "accel_z": az,
        "battery_mv": battery_mv,
    }


_DECODERS = {
    APID_TM_HEARTBEAT: decode_heartbeat,
    APID_TM_BME280: decode_bme280,
    APID_TM_LIS2DH: decode_lis2dh,
    APID_TM_POWER: decode_power,
    APID_TM_GPS: decode_gps_sim,
    APID_TM_ALL_SENSORS: decode_all_sensors,
}

FLIGHT_MODE_LABELS = {
    0: "IDLE",
    1: "NOMINAL",
    2: "SAFE",
    3: "DEBUG",
}


def decode_tm_payload(apid: int, payload: bytes) -> dict:
    decoder = _DECODERS.get(apid)
    if decoder:
        return decoder(payload)
    return {"raw": payload}


def flight_mode_name(mode: int | None) -> str:
    if mode is None:
        return "UNKNOWN"
    return FLIGHT_MODE_LABELS.get(mode, "UNKNOWN")


_mock_seq_count = 0


def generate_mock_telemetry() -> dict:
    global _mock_seq_count
    apid = random.choice([APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH])
    timestamp = int(time.time()) & 0xFFFFFFFF

    if apid == APID_TM_HEARTBEAT:
        payload = struct.pack(
            "<BIHBBHH",
            CCSDS_SPACECRAFT_ID,
            timestamp,
            random.randint(3300, 4200),
            random.randint(0, 2),
            0,
            random.randint(0, 500),
            random.randint(0, 5),
        )
    elif apid == APID_TM_BME280:
        payload = struct.pack("<hIB", random.randint(2000, 3500), random.randint(10100, 10200), random.randint(40, 60))
    else:
        payload = struct.pack("<hhh", random.randint(-50, 50), random.randint(-50, 50), random.randint(950, 1050))

    frame = build_tm(apid, payload, seq_count=_mock_seq_count, timestamp=timestamp)
    _mock_seq_count = (_mock_seq_count + 1) & 0x3FFF

    decoded = decode_tm_payload(apid, payload)
    return {"apid": apid, "timestamp": timestamp, "frame": frame, "raw_hex": frame.hex(), "decoded": decoded}
