from core.state import GroundStationState
from core.constants import ConnectionMode


def test_initial_state():
    state = GroundStationState()
    assert state.connection_mode == ConnectionMode.SIMULATED
    assert state.device is None
    assert state.mock_running is False


def test_set_simulated():
    state = GroundStationState()
    state.set_simulated()
    assert state.connection_mode == ConnectionMode.SIMULATED
    assert state.device is None


def test_set_hardware():
    state = GroundStationState()
    state.set_hardware("fake_device")
    assert state.connection_mode == ConnectionMode.HARDWARE
    assert state.device == "fake_device"


def test_is_simulated():
    state = GroundStationState()
    assert state.is_simulated is True
    state.set_hardware("dev")
    assert state.is_simulated is False


def test_mock_telemetry_control():
    state = GroundStationState()
    state.start_mock()
    assert state.mock_running is True
    state.stop_mock()
    assert state.mock_running is False
