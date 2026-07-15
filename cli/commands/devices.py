"""List all connected FlatSat boards and their endpoints."""

from cli.session import flatsat_get_devices
from cli.ui.banner import print_banner, print_title
from cli.ui.tables import print_devices_table

NAME = "devices"
NEEDS_DEVICE = False


def add_parser(subparsers):
    subparsers.add_parser(NAME, help="List all connected FlatSat boards and their endpoints.")


def run(args, dev=None):
    print_banner()
    devices = flatsat_get_devices()
    if not devices:
        print_title("CONNECTED FLATSAT DEVICES")
        print("  No FlatSat devices detected.")
    else:
        print_devices_table(devices)
    print()
