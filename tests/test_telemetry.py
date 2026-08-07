import struct

from core.constants import APID_TM_BME280, APID_TM_HEARTBEAT, APID_TM_LIS2DH
from core.telemetry import (
    decode_bme280,
    decode_heartbeat,
    decode_lis2dh,
    decode_tm_payload,
    generate_mock_telemetry,
)


def test_decode_heartbeat():
    # Payloads are little-endian (RP2040 native)
    payload = struct.pack("<BIHBBHH", 2, 1000, 3700, 1, 0, 42, 0)
    result = decode_heartbeat(payload)
    assert result["sc_id"] == 2
    assert result["uptime"] == 1000
    assert result["battery_mv"] == 3700
    assert result["flight_mode"] == 1
    assert result["difficulty"] == 0
    assert result["tc_count"] == 42
    assert result["error_count"] == 0


def test_decode_bme280():
    # press_x10 is deci-Pascals: 1013250 dPa == 101325 Pa == 1013.25 hPa
    payload = struct.pack("<hIB", 2550, 1013250, 55)
    result = decode_bme280(payload)
    assert result["temperature"] == 25.50
    assert result["pressure"] == 1013.25
    assert result["humidity"] == 55


def test_decode_lis2dh():
    payload = struct.pack("<hhh", 100, -200, 980)
    result = decode_lis2dh(payload)
    assert result["accel_x"] == 100
    assert result["accel_y"] == -200
    assert result["accel_z"] == 980


def test_decode_tm_payload_heartbeat():
    payload = struct.pack("<BIHBBHH", 2, 500, 3600, 0, 1, 10, 0)
    result = decode_tm_payload(APID_TM_HEARTBEAT, payload)
    assert result["sc_id"] == 2


def test_decode_tm_payload_unknown_apid():
    result = decode_tm_payload(0x099, b"\x01\x02\x03")
    assert result["raw"] == b"\x01\x02\x03"


def test_generate_mock_telemetry():
    tm = generate_mock_telemetry()
    assert "apid" in tm
    assert "timestamp" in tm
    assert "frame" in tm
    assert "decoded" in tm
    assert tm["apid"] in (APID_TM_HEARTBEAT, APID_TM_BME280, APID_TM_LIS2DH)
