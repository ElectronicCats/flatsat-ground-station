"""Banner and header rendering."""

import os
import platform
import random

from rich.panel import Panel

from cli import __version__
from cli.ui.output import STYLES, console

# APP Information
VERSION_NUMBER = __version__
COMPANY = "Electronic Cats - PWNLAB"

_FUNNY_PHRASES = [
    "Your FlatSat control terminal.",
    "Ground control to Major Cat.",
    "In space, no one can hear your serial port.",
    "Telemetry doesn't lie. Firmware does.",
    "Houston, we have a NeoPixel.",
    "Flying a satellite from your desk since 2024.",
    "Orbit not included.",
    "The only satellite that fits on a table.",
    "Downlink the cats, uplink the chaos.",
    "915 MHz and dreams of orbit.",
    "CCSDS: because space needs headers too.",
    "Safe mode is a state of mind.",
    "Space is hard. USB is harder.",
    "Every packet is a little postcard from orbit.",
    "Keep calm and check your link budget.",
    "It's not a bug, it's a solar flare.",
    "Nominal is the new exciting.",
    "Your desk is now a ground station.",
]

FUNNY_PHRASE = random.choice(_FUNNY_PHRASES)


def print_banner(module=None):
    """Print the ASCII art header."""
    if module:
        label = f"flatsat {module}"
    elif platform.system() != "Windows" and os.geteuid() == 0:
        label = "flatsat: (root)"
    else:
        label = "flatsat"

    ascii_art = f"""      :=--             --=-       |
      -====-         -=====       |
      :===================-       |
       ===================:       |
  -   :==--===========--==-   -   |  {label}
 -===:===-   :=====-   -==-.-=--  |  v{VERSION_NUMBER}
--    ====-   :===-   -====    -- |  {FUNNY_PHRASE}
-=:   :===================-   .=- |
 ---=-- -===============-  -=---  |
 ---       --=======--        --  |"""

    colored_ascii = f"[magenta bold]{ascii_art}[/magenta bold]"

    header_panel = Panel(
        colored_ascii,
        title=f"[magenta]{COMPANY}[/magenta]",
        border_style=STYLES["header"],
        title_align="left",
        padding=(1, 2),
    )
    console.print(header_panel)
