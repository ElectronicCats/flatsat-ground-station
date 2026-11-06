"""Banner and header rendering."""

import os
import random

from rich.markup import escape
from rich.panel import Panel

from modules.utils._version import __version__
from modules.utils.output import STYLES, console

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


def _running_as_root():
    # os.geteuid() does not exist on Windows, and not on every non-Windows
    # platform either, so feature-detect it rather than testing the OS name.
    return hasattr(os, "geteuid") and os.geteuid() == 0


def pick_phrase():
    """Choose a banner phrase. Called per render so output stays reproducible
    under test when the caller seeds `random`."""
    return random.choice(_FUNNY_PHRASES)


def print_banner(module=None):
    """Print the ASCII art header."""
    if module:
        label = escape(f"flatsat {module}")
    elif _running_as_root():
        label = "flatsat: (root)"
    else:
        label = "flatsat"

    ascii_art = f"""      :=--             --=-       |
      -====-         -=====       |
      :===================-       |
       ===================:       |
  -   :==--===========--==-   -   |  {label}
 -===:===-   :=====-   -==-.-=--  |  v{VERSION_NUMBER}
--    ====-   :===-   -====    -- |  {pick_phrase()}
-=:   :===================-   .=- |
 ---=-- -===============-  -=---  |
 ---       --=======--        --  |"""

    colored_ascii = f"[cyan bold]{ascii_art}[/cyan bold]"

    header_panel = Panel(
        colored_ascii,
        title=f"[cyan]{COMPANY}[/cyan]",
        border_style=STYLES["header"],
        title_align="left",
        padding=(1, 2),
    )
    console.print(header_panel)
