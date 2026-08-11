"""Get or set flight operational state.

Mirrors the web app's /api/satellite/flight logic (webapp/app.py
api_satellite_flight): the action depends on the role of the connected board.

- Satellite role: the `flight <state>` shell command is sent directly to the
  board over USB.
- Ground station role: a CCSDS command telecommand is built, SDLS-protected
  with the current difficulty, and transmitted over RF (Radio 1) to the remote
  satellite; the state is then also set locally on the ground station board.
"""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_error, print_info, print_success, print_warning
from core.constants import TC_OP_NOP, TC_OP_SET_DEBUG, TC_OP_SET_NOMINAL, TC_OP_SET_SAFE_MODE
from core.shell_parser import parse_difficulty, parse_mode

FLIGHT_STATES = ["idle", "nominal", "safe", "debug"]

# Flight state -> telecommand opcode (payload byte 0 of APID_TC_COMMAND).
# Kept in sync with webapp/app.py api_satellite_flight() opcode_map.
FLIGHT_OPCODES = {
    "idle": TC_OP_NOP,
    "nominal": TC_OP_SET_NOMINAL,
    "safe": TC_OP_SET_SAFE_MODE,
    "debug": TC_OP_SET_DEBUG,
}


def _detect_local_role(dev):
    """Infer whether the connected board acts as satellite or ground station.

    Replicates webapp/app.py _local_mode_from_shell()/_local_role_from_mode():
    a board with Radio 1 that is not explicitly in satellite/mission mode is a
    ground station (the default dual-radio operating role).
    """
    mode_raw = dev.send_shell_command_full("mode")
    status_raw = dev.send_shell_command_full("status")
    mode = parse_mode(mode_raw)

    if mode == "satellite":
        local_mode = "satellite"
    elif status_raw and "Radio0: LoRa  mode=command" in status_raw:
        local_mode = "ground_station"
    elif mode == "raw":
        local_mode = "raw" if (status_raw and "mode=stream" in status_raw) else "ground_station"
    else:
        local_mode = mode

    # If board is in gs/ground_station mode, or is a dual-radio board not in satellite/mission mode, it acts as a ground station.
    if local_mode in ("ground_station", "gs") or (getattr(dev, "has_radio1", True) and local_mode not in ("satellite", "mission")):
        return "ground_station"
    return "satellite" if local_mode in ("satellite", "mission") else "ground_station"


def _send_flight_over_rf(dev, value, difficulty):
    """Build, protect and transmit a flight telecommand over RF (ground station path)."""
    from core.ccsds import sdls_protect_frame
    from core.radio_bridge import RadioBridge
    from core.state import GroundStationState
    from core.telecommand import build_command_tc

    frame = build_command_tc(FLIGHT_OPCODES[value])
    frame = sdls_protect_frame(frame, difficulty)

    # RadioBridge reads the device, active_radio and difficulty from a
    # GroundStationState; build a minimal hardware state around the connected
    # board so the CLI transmits through the same path as the webapp.
    gs = GroundStationState()
    gs.set_hardware(dev)
    gs.difficulty = difficulty

    return RadioBridge(gs).send_raw(frame)


@click.command("flight")
@click.argument("value", required=False, type=click.Choice(FLIGHT_STATES))
@click.option(
    "--difficulty",
    "difficulty_override",
    type=click.IntRange(0, 3),
    default=None,
    help="SDLS level for the RF telecommand (ground station only). Defaults to the board's difficulty.",
)
@with_device
def flight(dev, value, difficulty_override):
    """Get or set flight operational state (idle, nominal, safe, debug)

    \b
        flatsat flight                    # query current flight state
        flatsat flight nominal            # satellite: set connected board to NOMINAL
        flatsat flight nominal            # ground station: send NOMINAL as an RF telecommand
        flatsat flight safe --difficulty 3
    """
    if not value:
        output = send_cmd(dev, "flight")
        print_info(f"Flight State: {output.strip() if output else '(no response)'}")
        return

    role = _detect_local_role(dev)

    if role != "ground_station":
        # Satellite role: command the connected board directly over the shell.
        output = send_cmd(dev, f"flight {value}")
        print_success(f"Flight state set to '{value}': {output.strip() if output else 'OK'}")
        return

    # Ground station role: transmit the flight state as an RF telecommand.
    if difficulty_override is not None:
        difficulty = difficulty_override
    else:
        difficulty = parse_difficulty(dev.send_shell_command_full("difficulty"))

    print_info(f"Ground station detected. Sending flight TC '{value}' over RF (SDLS level {difficulty})...")
    result = _send_flight_over_rf(dev, value, difficulty)

    if result.get("status") == "error":
        print_error(f"Flight TC failed: {result.get('error')}")
        return

    # Mirror the webapp: also set the state locally on the ground station board.
    send_cmd(dev, f"flight {value}")

    detail = f" ({result.get('bytes', 0)} bytes, {result.get('response', 'OK')})" if result.get("status") == "sent" else ""
    print_success(f"Flight TC '{value}' transmitted over RF{detail}.")
    if result.get("status") == "sent_simulated":
        print_warning("Transmitted in simulated mode (no radio hardware).")
