"""Command registry.

Each command module exposes:
  NAME          -> subcommand string
  NEEDS_DEVICE  -> whether app.py should connect a device before run()
  add_parser(subparsers)
  run(args, dev)   (dev is None when NEEDS_DEVICE is False)

To add a new command: create a module here and append it to COMMANDS.
"""

from . import (
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
    config,
)

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
    config,
]

BY_NAME = {m.NAME: m for m in COMMANDS}
