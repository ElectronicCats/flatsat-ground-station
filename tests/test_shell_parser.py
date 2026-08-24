from core.shell_parser import (
    parse_difficulty,
    parse_flight,
    parse_fw_version,
    parse_lora_config,
    parse_mode,
    parse_sc_id,
    parse_sensors,
)


def test_parse_fw_version():
    raw = """fw_versionFW: dev-c6512ae-dirty
Git: c6512ae (dirty)
Built: 2026-04-10T00:31:46Z
Compiler: GNU 12.2.0"""
    result = parse_fw_version(raw)
    assert result["fw_version"] == "dev-c6512ae-dirty"
    assert result["git_sha"] == "c6512ae"
    assert result["git_dirty"] is True
    assert result["build_date"] == "2026-04-10T00:31:46Z"


def test_parse_fw_version_clean():
    raw = """fw_versionFW: v1.0.0
Git: abc1234 (clean)
Built: 2026-04-10T00:00:00Z
Compiler: GNU 12.2.0"""
    result = parse_fw_version(raw)
    assert result["fw_version"] == "v1.0.0"
    assert result["git_dirty"] is False


def test_parse_flight():
    raw = "flightflight: NOMINAL  battery: 3694 mV  tm_rate: 10 sec"
    result = parse_flight(raw)
    assert result["flight"] == "NOMINAL"
    assert result["battery_mv"] == 3694
    assert result["tm_rate"] == 10


def test_parse_flight_safe():
    raw = "flightflight: SAFE  battery: 2999 mV  tm_rate: 10 sec"
    result = parse_flight(raw)
    assert result["flight"] == "SAFE"
    assert result["battery_mv"] == 2999


def test_parse_mode():
    assert parse_mode("modemode: mission") == "satellite"
    assert parse_mode("modemode: raw") == "raw"
    assert parse_mode("modemode: tinygs") == "tinygs"
    assert parse_mode("role: ground_station") == "ground_station"
    assert parse_mode("role: satellite") == "satellite"
    assert parse_mode("role: gs") == "ground_station"
    assert parse_mode("role: sat") == "satellite"
    assert parse_mode("mode: gs") == "ground_station"
    assert parse_mode("mode: sat") == "satellite"


def test_parse_difficulty():
    assert parse_difficulty("difficultydifficulty: 1 (normal)") == 1
    assert parse_difficulty("difficultydifficulty: 0 (training)") == 0
    assert parse_difficulty("difficultydifficulty: 3 (blue_team)") == 3


def test_parse_sc_id():
    assert parse_sc_id("sc_idspacecraft_id: 0x02") == 2
    assert parse_sc_id("sc_idspacecraft_id: 0xFF") == 255
    assert parse_sc_id("sc_idspacecraft_id: 10") == 10


def test_parse_sensors():
    raw = """sensorsAccel: x=15 mg  y=-8 mg  z=1012 mg
Temp:  25.340 C
Press: 101325 Pa
Humid: 48%"""
    result = parse_sensors(raw)
    assert result["accel_x"] == 15
    assert result["accel_y"] == -8
    assert result["accel_z"] == 1012
    assert result["temperature"] == 25.340
    assert result["pressure"] == 1013.25  # shell reports Pa, parser normalizes to hPa
    assert result["humidity"] == 48


def test_parse_lora_config():
    raw = """lora_config R0LoRa Configuration [Radio 0]:
  Frequency: 915000000 Hz
  Spreading Factor: SF12
  Bandwidth: 250 kHz
  Coding Rate: 4/5
  TX Power: 20 dBm
  Preamble Length: 12
  IQ: Normal
  Sync Word: Private (0x12)
  Mode: Stream"""
    result = parse_lora_config(raw)
    assert result["frequency"] == 915000000
    assert result["sf"] == 12
    assert result["bw"] == 250
    assert result["cr"] == "4/5"
    assert result["power"] == 20
    assert result["preamble"] == 12
    assert result["syncword"] == "0x12"
    assert result["iq"] == "Normal"


def test_parse_flight_none():
    assert parse_flight(None) == {
        "flight": "unknown",
        "battery_mv": 0,
        "tm_rate": 0,
        "uptime": None,
        "tc_count": None,
        "error_count": None,
    }


def test_parse_flight_with_counters():
    raw = "flightflight: NOMINAL  battery: 3694 mV  tm_rate: 10 sec\nuptime: 1234 sec\ntc_count: 5\nerror_count: 2\n"
    result = parse_flight(raw)
    assert result["flight"] == "NOMINAL"
    assert result["battery_mv"] == 3694
    assert result["tm_rate"] == 10
    assert result["uptime"] == 1234
    assert result["tc_count"] == 5
    assert result["error_count"] == 2



def test_parse_sensors_none():
    result = parse_sensors(None)
    assert result["temperature"] == 0
