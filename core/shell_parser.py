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
        return {"flight": "unknown", "battery_mv": 0, "tm_rate": 0}

    result = {"flight": "unknown", "battery_mv": 0, "tm_rate": 0}

    flight_match = re.search(r"flight:\s*(\w+)", raw)
    if flight_match:
        result["flight"] = flight_match.group(1)

    batt_match = re.search(r"battery:\s*(\d+)\s*mV", raw)
    if batt_match:
        result["battery_mv"] = int(batt_match.group(1))

    rate_match = re.search(r"tm_rate:\s*(\d+)\s*sec", raw)
    if rate_match:
        result["tm_rate"] = int(rate_match.group(1))

    return result


def parse_mode(raw: str | None) -> str:
    if not raw:
        return "unknown"
    match = re.search(r"mode:\s*(\w+)", raw)
    return match.group(1) if match else "unknown"


def parse_difficulty(raw: str | None) -> int:
    if not raw:
        return 0
    match = re.search(r"difficulty:\s*(\d+)", raw)
    return int(match.group(1)) if match else 0


def parse_sc_id(raw: str | None) -> int:
    if not raw:
        return 0
    match = re.search(r"sc_id:\s*(\d+)", raw)
    return int(match.group(1)) if match else 0


def parse_sensors(raw: str | None) -> dict:
    defaults = {
        "accel_x": 0,
        "accel_y": 0,
        "accel_z": 0,
        "temperature": 0,
        "pressure": 0,
        "humidity": 0,
    }
    if not raw:
        return defaults

    result = dict(defaults)

    accel_match = re.search(r"x=(-?\d+)\s*mg\s+y=(-?\d+)\s*mg\s+z=(-?\d+)\s*mg", raw)
    if accel_match:
        result["accel_x"] = int(accel_match.group(1))
        result["accel_y"] = int(accel_match.group(2))
        result["accel_z"] = int(accel_match.group(3))

    temp_match = re.search(r"Temp:\s*([\d.]+)\s*C", raw)
    if temp_match:
        result["temperature"] = float(temp_match.group(1))

    press_match = re.search(r"Press:\s*(\d+)\s*Pa", raw)
    if press_match:
        result["pressure"] = int(press_match.group(1))

    humid_match = re.search(r"Humid:\s*(\d+)%", raw)
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

    sf_match = re.search(r"SF:\s*(\d+)", raw)
    if sf_match:
        result["sf"] = int(sf_match.group(1))

    bw_match = re.search(r"BW:\s*(\d+)\s*kHz", raw)
    if bw_match:
        result["bw"] = int(bw_match.group(1))

    cr_match = re.search(r"CR:\s*([\d/]+)", raw)
    if cr_match:
        result["cr"] = cr_match.group(1)

    power_match = re.search(r"Power:\s*(-?\d+)\s*dBm", raw)
    if power_match:
        result["power"] = int(power_match.group(1))

    preamble_match = re.search(r"Preamble:\s*(\d+)", raw)
    if preamble_match:
        result["preamble"] = int(preamble_match.group(1))

    sw_match = re.search(r"SyncWord:\s*(0x\w+)", raw)
    if sw_match:
        result["syncword"] = sw_match.group(1)

    iq_match = re.search(r"IQ:\s*(\w+)", raw)
    if iq_match:
        result["iq"] = iq_match.group(1)

    return result
