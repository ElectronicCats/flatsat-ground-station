"""FlatSat ground station state management."""

from typing import Any, Optional

from core.constants import ConnectionMode


class GroundStationState:
    def __init__(self):
        self.connection_mode: ConnectionMode = ConnectionMode.SIMULATED
        self.device: Optional[Any] = None
        self.mock_running: bool = False

    @property
    def is_simulated(self) -> bool:
        return self.connection_mode == ConnectionMode.SIMULATED

    def set_simulated(self):
        self.connection_mode = ConnectionMode.SIMULATED
        self.device = None

    def set_hardware(self, device: Any):
        self.connection_mode = ConnectionMode.HARDWARE
        self.device = device

    def start_mock(self):
        self.mock_running = True

    def stop_mock(self):
        self.mock_running = False
