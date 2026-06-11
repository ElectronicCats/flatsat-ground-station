"""FlatSat ground station state management."""

import time
from typing import Any

from core.constants import APID_TM_ALL_SENSORS, APID_TM_BME280, APID_TM_HEARTBEAT, APID_TM_LIS2DH, ConnectionMode
from core.telemetry import flight_mode_name


def _empty_remote_satellite() -> dict:
    return {
        "available": False,
        "source": None,
        "last_seen_ts": None,
        "last_apid": None,
        "sc_id": None,
        "flight": None,
        "difficulty": None,
        "battery_mv": None,
        "uptime": None,
        "tc_count": None,
        "error_count": None,
        "temperature": None,
        "pressure": None,
        "humidity": None,
        "accel_x": None,
        "accel_y": None,
        "accel_z": None,
        "rssi": None,
        "snr": None,
    }


class GroundStationState:
    def __init__(self):
        self.connection_mode: ConnectionMode = ConnectionMode.IDLE
        self.device: Any | None = None
        self.mock_running: bool = False
        self.difficulty: int = 0
        self.active_radio: int = 0
        self.remote_satellite: dict = _empty_remote_satellite()
        self.forced_radio_mode: str = "auto"
        self.forced_device_role: str = "auto"
        self.local_device_info: dict = {
            "fw_version": None,
            "git_sha": None,
            "git_dirty": None,
            "build_date": None,
            "sc_id": None,
            "mode": None,
            "flight": None,
            "difficulty": 0,
            "radio_configs": {
                "R0": {"frequency": 0, "sf": 0, "bw": 0, "power": 0},
                "R1": {"frequency": 0, "sf": 0, "bw": 0, "power": 0},
            }
        }

    @property
    def is_idle(self) -> bool:
        return self.connection_mode == ConnectionMode.IDLE

    @property
    def is_simulated(self) -> bool:
        return self.connection_mode == ConnectionMode.SIMULATED

    @property
    def is_hardware(self) -> bool:
        return self.connection_mode == ConnectionMode.HARDWARE

    def set_idle(self):
        self.connection_mode = ConnectionMode.IDLE
        self.device = None
        self.mock_running = False
        self.difficulty = 0
        self.active_radio = 0
        self.reset_remote_satellite()
        self.forced_radio_mode = "auto"
        self.forced_device_role = "auto"
        self.local_device_info = {
            "fw_version": None,
            "git_sha": None,
            "git_dirty": None,
            "build_date": None,
            "sc_id": None,
            "mode": None,
            "flight": None,
            "difficulty": 0,
            "radio_configs": {
                "R0": {"frequency": 0, "sf": 0, "bw": 0, "power": 0},
                "R1": {"frequency": 0, "sf": 0, "bw": 0, "power": 0},
            }
        }

    def set_simulated(self):
        self.connection_mode = ConnectionMode.SIMULATED
        self.device = None
        self.active_radio = 0
        self.reset_remote_satellite()
        self.local_device_info = {
            "fw_version": None,
            "git_sha": None,
            "git_dirty": None,
            "build_date": None,
            "sc_id": None,
            "mode": None,
            "flight": None,
            "difficulty": 0,
            "radio_configs": {
                "R0": {"frequency": 0, "sf": 0, "bw": 0, "power": 0},
                "R1": {"frequency": 0, "sf": 0, "bw": 0, "power": 0},
            }
        }

    def set_hardware(self, device: Any):
        self.connection_mode = ConnectionMode.HARDWARE
        self.device = device
        # Default to Dual (2) if device has radio1, otherwise Radio 0 (0)
        self.active_radio = 2 if getattr(device, "has_radio1", True) else 0
        self.reset_remote_satellite()
        self.local_device_info = {
            "fw_version": None,
            "git_sha": None,
            "git_dirty": None,
            "build_date": None,
            "sc_id": None,
            "mode": None,
            "flight": None,
            "difficulty": 0,
            "radio_configs": {
                "R0": {"frequency": 0, "sf": 0, "bw": 0, "power": 0},
                "R1": {"frequency": 0, "sf": 0, "bw": 0, "power": 0},
            }
        }

    def start_mock(self):
        self.mock_running = True

    def stop_mock(self):
        self.mock_running = False

    def reset_remote_satellite(self):
        self.remote_satellite = _empty_remote_satellite()

    def update_remote_satellite(self, apid: int, decoded: dict, rssi=None, snr=None, source: str = "radio0", timestamp=None):
        snapshot = self.remote_satellite
        snapshot["available"] = True
        snapshot["source"] = source
        snapshot["last_seen_ts"] = time.time()
        snapshot["last_apid"] = apid

        if rssi is not None:
            snapshot["rssi"] = rssi
        if snr is not None:
            snapshot["snr"] = snr
        if timestamp is not None:
            snapshot["uptime"] = timestamp

        if apid == APID_TM_HEARTBEAT:
            snapshot["sc_id"] = decoded.get("sc_id")
            snapshot["flight"] = flight_mode_name(decoded.get("flight_mode"))
            snapshot["difficulty"] = decoded.get("difficulty")
            snapshot["battery_mv"] = decoded.get("battery_mv")
            snapshot["uptime"] = decoded.get("uptime")
            snapshot["tc_count"] = decoded.get("tc_count")
            snapshot["error_count"] = decoded.get("error_count")
        elif apid == APID_TM_BME280:
            snapshot["temperature"] = decoded.get("temperature")
            snapshot["pressure"] = decoded.get("pressure")
            snapshot["humidity"] = decoded.get("humidity")
        elif apid == APID_TM_LIS2DH:
            snapshot["accel_x"] = decoded.get("accel_x")
            snapshot["accel_y"] = decoded.get("accel_y")
            snapshot["accel_z"] = decoded.get("accel_z")
        elif apid == APID_TM_ALL_SENSORS:
            snapshot["temperature"] = decoded.get("temperature")
            snapshot["pressure"] = decoded.get("pressure")
            snapshot["humidity"] = decoded.get("humidity")
            snapshot["accel_x"] = decoded.get("accel_x")
            snapshot["accel_y"] = decoded.get("accel_y")
            snapshot["accel_z"] = decoded.get("accel_z")
            snapshot["battery_mv"] = decoded.get("battery_mv")
            if snapshot["sc_id"] is None:
                snapshot["sc_id"] = 0x02
            if snapshot["flight"] is None:
                snapshot["flight"] = "NOMINAL"
            if snapshot["difficulty"] is None:
                snapshot["difficulty"] = self.difficulty
            if snapshot["tc_count"] is None:
                snapshot["tc_count"] = 0
            if snapshot["error_count"] is None:
                snapshot["error_count"] = 0

    def get_remote_satellite_snapshot(self, stale_after: float = 12.0) -> dict:
        snapshot = dict(self.remote_satellite)
        last_seen_ts = snapshot.get("last_seen_ts")
        age_sec = None if last_seen_ts is None else max(0.0, time.time() - last_seen_ts)
        snapshot["age_sec"] = age_sec
        snapshot["stale"] = age_sec is None or age_sec > stale_after
        return snapshot
