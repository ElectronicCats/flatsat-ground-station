"""
Command registry backward-compatibility module.

Exports commands defined in cli.cli.
"""

from cli.cli import (
    attack,
    cmd,
    color,
    completion,
    config,
    devices,
    difficulty,
    flight,
    identify,
    mode,
    reboot,
    replay,
    sensors,
    sniff,
    status,
    tc,
    transmit,
)
from cli.cli import (
    console_cmd as console,
)

COMMANDS = [
    devices,
    console,
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
    tc,
    attack,
    config,
    completion,
]
