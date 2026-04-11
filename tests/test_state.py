from core.constants import APID_TM_HEARTBEAT, ConnectionMode
from core.state import GroundStationState


def test_initial_state():
    state = GroundStationState()
    assert state.connection_mode == ConnectionMode.IDLE
    assert state.is_idle is True
    assert state.device is None
    assert state.mock_running is False


def test_set_simulated():
    state = GroundStationState()
    state.set_simulated()
    assert state.connection_mode == ConnectionMode.SIMULATED
    assert state.is_simulated is True
    assert state.device is None


def test_set_hardware():
    state = GroundStationState()
    state.set_hardware("fake_device")
    assert state.connection_mode == ConnectionMode.HARDWARE
    assert state.is_hardware is True
    assert state.device == "fake_device"


def test_set_idle():
    state = GroundStationState()
    state.set_hardware("dev")
    state.set_idle()
    assert state.is_idle is True
    assert state.device is None
    assert state.mock_running is False


def test_is_simulated():
    state = GroundStationState()
    assert state.is_simulated is False  # starts IDLE
    state.set_simulated()
    assert state.is_simulated is True
    state.set_hardware("dev")
    assert state.is_simulated is False


def test_mock_telemetry_control():
    state = GroundStationState()
    state.start_mock()
    assert state.mock_running is True
    state.stop_mock()
    assert state.mock_running is False


def test_remote_satellite_snapshot_updates_from_heartbeat():
    state = GroundStationState()
    state.update_remote_satellite(
        APID_TM_HEARTBEAT,
        {
            "sc_id": 2,
            "flight_mode": 1,
            "difficulty": 3,
            "battery_mv": 3660,
            "uptime": 120,
            "tc_count": 8,
            "error_count": 1,
        },
        rssi=-72,
        snr=9.5,
    )
    snapshot = state.get_remote_satellite_snapshot(stale_after=999)
    assert snapshot["available"] is True
    assert snapshot["flight"] == "NOMINAL"
    assert snapshot["battery_mv"] == 3660
    assert snapshot["tc_count"] == 8
    assert snapshot["rssi"] == -72
    assert snapshot["snr"] == 9.5
    assert snapshot["stale"] is False


def test_set_idle_clears_remote_snapshot():
    state = GroundStationState()
    state.update_remote_satellite(APID_TM_HEARTBEAT, {"flight_mode": 2})
    state.set_idle()
    snapshot = state.get_remote_satellite_snapshot()
    assert snapshot["available"] is False
    assert snapshot["flight"] is None
