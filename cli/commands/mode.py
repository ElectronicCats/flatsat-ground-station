"""Get or set satellite operation mode.

Mirrors the web app's /api/satellite/mode logic (webapp/app.py): the board's
role is driven by the Radio 0/1 lora_mode (stream vs command), while `mode
sat/gs` is sent for firmware compatibility. TinyGS spoofing is handled here too,
matching the /api/satellite/tinygs flow.
"""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info, print_success, print_warning

# Web-app mode name -> the shell command sequence sent to the board.
# Kept in sync with webapp/app.py api_satellite_mode().
MODE_SEQUENCES = {
    # Satellite / mission: MIXED radio modes.
    #   R1 stream  -> transmits telemetry/beacons (firmware auto-beacon).
    #   R0 command -> receives telecommands. A receptor MUST be in command mode
    #                 to demodulate/parse incoming frames (see docs
    #                 hardware-mode-design.md:101); with R0 in stream the
    #                 satellite never processes the uplink. Do NOT use
    #                 `lora_mode ALL stream` here: it clobbers R0's command mode.
    "mission": ["mode sat", "lora_mode R1 stream", "lora_mode R0 command"],
    "sat": ["mode sat", "lora_mode R1 stream", "lora_mode R0 command"],
    # Ground station: radios in command mode (role inferred as ground station).
    "ground_station": ["mode gs", "lora_apply ALL", "lora_mode ALL command"],
    "gs": ["mode gs", "lora_apply ALL", "lora_mode ALL command"],
    # Raw ground station: firmware in gs but radios streaming.
    "raw": ["mode gs", "lora_mode ALL stream"],
}


@click.command("mode")
@click.argument(
    "value",
    required=False,
    type=click.Choice(["mission", "sat", "ground_station", "gs", "raw", "tinygs"]),
)
@click.option("--profile", default="norbi", show_default=True, help="TinyGS profile to spoof (only with 'tinygs').")
@with_device
def mode(dev, value, profile):
    """Get or set satellite operation mode

    \b
        flatsat mode mission          # satellite role (radios stream)
        flatsat mode ground_station   # ground station role (radios command)
        flatsat mode raw              # gs firmware, radios stream
        flatsat mode tinygs --profile norbi
    """
    if not value:
        output = send_cmd(dev, "status")
        print_info(f"Current status info: {output.strip() if output else '(no response)'}")
        return

    if value == "tinygs":
        send_cmd(dev, "lora_mode ALL stream")
        output = send_cmd(dev, f"tinygs spoof {profile}")
        print_success(f"TinyGS spoofing '{profile}': {output.strip() if output else 'OK'}")
        return

    for cmd in MODE_SEQUENCES[value]:
        output = send_cmd(dev, cmd)
        print_info(f"{cmd} -> {output.strip() if output else 'OK'}")

    print_success(f"Mode set to '{value}'.")
    print_info("Identifying the board that changed mode (blinking LEDs)...")
    ident = send_cmd(dev, "identify")
    if ident:
        print_warning(ident.strip())
