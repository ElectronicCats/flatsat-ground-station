"""FlatSat Ground Station — shared core library.

Usage:
    from core import build_tm, parse_frame, generate_mock_telemetry
    from core.constants import APID_TM_HEARTBEAT, TC_OP_PING
"""

from core.ccsds import (
    CcsdsPacket,
    build_tc,
    build_tm,
    ccsds_crc16,
    parse_frame,
)
from core.state import GroundStationState
from core.telecommand import (
    build_command_tc,
    build_privileged_tc,
)
from core.telemetry import (
    decode_tm_payload,
    generate_mock_telemetry,
)
