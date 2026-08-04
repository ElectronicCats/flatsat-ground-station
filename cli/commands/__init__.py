"""Command registry.

Each module here exposes a single click command object named after the module.
Device-backed commands wrap their callback in `cli.session.with_device`, which
resolves and connects the board before the callback runs.

To add a new command: create a module here and append it to COMMANDS. app.py
registers everything in COMMANDS on the root group.
"""

from .cmd import cmd
from .color import color
from .completion import completion
from .config import config
from .devices import devices
from .difficulty import difficulty
from .flight import flight
from .identify import identify
from .mode import mode
from .reboot import reboot
from .replay import replay
from .sensors import sensors
from .sniff import sniff
from .status import status
from .transmit import transmit

COMMANDS = [
    devices,
    status,
    sensors,
    mode,
    flight,
    difficulty,
    color,
    identify,
    reboot,
    cmd,
    sniff,
    replay,
    transmit,
    config,
    completion,
]
