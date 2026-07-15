#!/usr/bin/env python3
"""FlatSat Host CLI: argument parsing and command dispatch.

Discovers subcommands from the cli.commands registry, resolves/connects a
device when needed, and delegates execution to the matching command module.
"""

import argparse
import sys

from cli import commands
from cli.session import get_selected_device
from cli.ui.help import print_help_menu


def build_parser():
    parser = argparse.ArgumentParser(
        description="FlatSat Host CLI - Manage and configure your FlatSat boards easily.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show this help menu and exit.")
    parser.add_argument("-s", "--serial", help="Serial number of the target FlatSat board.")
    parser.add_argument("-p", "--port", help="Force direct connection to a custom shell port (e.g. /dev/ttyACM3).")

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    for command in commands.COMMANDS:
        command.add_parser(subparsers)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.help or not args.command:
        print_help_menu()
        return

    command = commands.BY_NAME[args.command]

    # Commands that don't touch hardware (e.g. `devices`) run without connecting.
    if not command.NEEDS_DEVICE:
        command.run(args, None)
        return

    dev = get_selected_device(serial_number=args.serial, port=args.port)

    connection_res = dev.connect()
    if not connection_res.get("shell"):
        print("[-] Error: Failed to open Shell serial interface.")
        sys.exit(1)

    try:
        command.run(args, dev)
    finally:
        dev.disconnect()


if __name__ == "__main__":
    main()
