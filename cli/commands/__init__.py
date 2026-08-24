"""
Command registry backward-compatibility module.

Exports commands defined in cli.cli.
"""

from cli.cli import (
    color,
    cmd,
    completion,
    config,
    console_cmd as console,
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
    transmit,
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
    config,
    completion,
]
