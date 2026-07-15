"""Get or set satellite operation mode."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info


@click.command("mode")
@click.argument("value", required=False, type=click.Choice(["gs", "sat", "tinygs"]))
@with_device
def mode(dev, value):
    """Get or set satellite operation mode"""
    if value:
        output = send_cmd(dev, f"mode {value}")
        print_info(output.strip())
    else:
        output = send_cmd(dev, "status")
        # Parse active mode from status response
        print_info(f"Current status info: {output.strip()}")
