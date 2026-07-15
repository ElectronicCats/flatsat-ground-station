"""Read system status and firmware information."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_response, print_title


@click.command("status")
@with_device
def status(dev):
    """Read system status and firmware information"""
    print_title("SYSTEM STATUS")
    fw_version = send_cmd(dev, "fw_version")
    state = send_cmd(dev, "status")
    if fw_version:
        print_response(fw_version.strip())
    if state:
        print_response(state.strip())
