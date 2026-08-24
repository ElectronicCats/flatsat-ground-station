"""Parse FlatSat shell command responses into structured data.

Each shell response is prefixed with the echo of the command itself
(e.g., "flightflight: NOMINAL..."), so parsers handle that.
"""

import re


def parse_fw_version(raw: str | None) -> dict:
    if not raw:
        return {"fw_version": "unknown", "git_sha": "", "git_dirty": False, "build_date": ""}
    result = {"fw_version": "unknown", "git_sha": "", "git_dirty": False, "build_date": ""}

    fw_match = re.search(r"FW:\s*(.+)", raw)
    if fw_match:
        result["fw_version"] = fw_match.group(1).strip()

    git_match = re.search(r"Git:\s*(\w+)\s*\((\w+)\)", raw)
    if git_match:
        result["git_sha"] = git_match.group(1)
        result["git_dirty"] = git_match.group(2) == "dirty"

    built_match = re.search(r"Built:\s*(.+)", raw)
    if built_match:
        result["build_date"] = built_match.group(1).strip()

    return result


def parse_flight(raw: str | None) -> dict:
    if not raw:
        return {"flight": "unknown", "battery_mv": 0, "tm_rate": 0, "uptime": None, "tc_count": None, "error_count": None}

    result = {"flight": "unknown", "battery_mv": 0, "tm_rate": 0, "uptime": None, "tc_count": None, "error_count": None}

    flight_match = re.search(r"flight:\s*(\w+)", raw)
    if flight_match:
        result["flight"] = flight_match.group(1)

    batt_match = re.search(r"battery:\s*(\d+)\s*mV", raw)
    if batt_match:
        result["battery_mv"] = int(batt_match.group(1))

    rate_match = re.search(r"tm_rate:\s*(\d+)\s*sec", raw)
    if rate_match:
        result["tm_rate"] = int(rate_match.group(1))

    uptime_match = re.search(r"uptime:\s*(\d+)\s*sec", raw)
    if uptime_match:
        result["uptime"] = int(uptime_match.group(1))

    tc_match = re.search(r"tc_count:\s*(\d+)", raw)
    if tc_match:
        result["tc_count"] = int(tc_match.group(1))

    err_match = re.search(r"error_count:\s*(\d+)", raw)
    if err_match:
        result["error_count"] = int(err_match.group(1))

    return result


def parse_mode(raw: str | None) -> str:
    if not raw:
        return "unknown"
    match = re.search(r"(?:mode|role):\s*(\w+)", raw, re.IGNORECASE)
    if match:
        val = match.group(1).lower()
        if val in ("gs", "ground_station"):
            return "ground_station"
        if val in ("sat", "satellite", "mission"):
            return "satellite"
        return val
    return "unknown"


def parse_difficulty(raw: str | None) -> int:
    if not raw:
        return 0
    match = re.search(r"difficulty:\s*(\d+)", raw, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def parse_sc_id(raw: str | None) -> int:
    if not raw:
        return 0
    # Firmware responds "spacecraft_id: 0x02" (hex format)
    match = re.search(r"(?:spacecraft_id|sc_id):\s*(0x[0-9a-fA-F]+|\d+)", raw, re.IGNORECASE)
    if match:
        val = match.group(1)
        return int(val, 16) if val.lower().startswith("0x") else int(val)
    return 0


def parse_sensors(raw: str | None) -> dict:
    defaults = {
        "accel_x": 0,
        "accel_y": 0,
        "accel_z": 0,
        "temperature": 0.0,
        "pressure": 0.0,
        "humidity": 0,
    }
    if not raw:
        return defaults

    result = dict(defaults)

    accel_match = re.search(r"x=(-?\d+)\s*mg\s+y=(-?\d+)\s*mg\s+z=(-?\d+)\s*mg", raw, re.IGNORECASE)
    if accel_match:
        result["accel_x"] = int(accel_match.group(1))
        result["accel_y"] = int(accel_match.group(2))
        result["accel_z"] = int(accel_match.group(3))

    temp_match = re.search(r"Temp:\s*(-?[\d.]+)\s*C", raw, re.IGNORECASE)
    if temp_match:
        result["temperature"] = float(temp_match.group(1))

    # Shell prints Pascals; the pipeline stores hPa (same unit as the TM decoder).
    press_match = re.search(r"Press:\s*(\d+)\s*Pa", raw, re.IGNORECASE)
    if press_match:
        result["pressure"] = int(press_match.group(1)) / 100.0

    humid_match = re.search(r"Humid:\s*(\d+)%", raw, re.IGNORECASE)
    if humid_match:
        result["humidity"] = int(humid_match.group(1))

    return result



def parse_lora_config(raw: str | None) -> dict:
    defaults = {
        "frequency": 0,
        "sf": 0,
        "bw": 0,
        "cr": "",
        "power": 0,
        "preamble": 0,
        "syncword": "",
        "iq": "",
    }
    if not raw:
        return defaults

    result = dict(defaults)

    freq_match = re.search(r"Frequency:\s*(\d+)\s*Hz", raw)
    if freq_match:
        result["frequency"] = int(freq_match.group(1))

    # Matches both "SF: 7" and "Spreading Factor: SF12"
    sf_match = re.search(r"(?:Spreading Factor|SF):\s*(?:SF)?(\d+)", raw)
    if sf_match:
        result["sf"] = int(sf_match.group(1))

    # Matches both "BW: 125 kHz" and "Bandwidth: 250 kHz"
    bw_match = re.search(r"(?:Bandwidth|BW):\s*(\d+)\s*kHz", raw)
    if bw_match:
        result["bw"] = int(bw_match.group(1))

    # Matches both "CR: 4/5" and "Coding Rate: 4/5"
    cr_match = re.search(r"(?:Coding Rate|CR):\s*([\d/]+)", raw)
    if cr_match:
        result["cr"] = cr_match.group(1)

    power_match = re.search(r"Power:\s*(-?\d+)\s*dBm", raw)
    if power_match:
        result["power"] = int(power_match.group(1))

    # Matches both "Preamble: 12" and "Preamble Length: 12"
    preamble_match = re.search(r"Preamble(?:\s*Length)?:\s*(\d+)", raw)
    if preamble_match:
        result["preamble"] = int(preamble_match.group(1))

    # Matches both "SyncWord: 0x12" and "Sync Word: Private (0x12)"
    sw_match = re.search(r"(?:Sync\s*Word|SyncWord):\s*(?:\w+\s*\()?(0x\w+)", raw)
    if sw_match:
        result["syncword"] = sw_match.group(1)

    iq_match = re.search(r"IQ:\s*(\w+)", raw)
    if iq_match:
        result["iq"] = iq_match.group(1)

    return result
