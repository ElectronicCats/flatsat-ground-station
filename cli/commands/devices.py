"""List all connected FlatSat boards and their endpoints."""

import click

from cli.session import flatsat_get_devices
from cli.ui.output import print_title, print_warning
from cli.ui.tables import print_devices_table


@click.command("devices")
def devices():
    """List all connected FlatSat boards and their endpoints"""
    devs = flatsat_get_devices()
    if not devs:
        print_title("CONNECTED FLATSAT DEVICES")
        print_warning("No FlatSat devices detected.")
        return

    print_devices_table(devs)
