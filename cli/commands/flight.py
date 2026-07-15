"""Get or set flight operational state."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info


@click.command("flight")
@click.argument("value", required=False, type=click.Choice(["safe", "nominal", "idle", "debug"]))
@with_device
def flight(dev, value):
    """Get or set flight operational state"""
    if value:
        output = send_cmd(dev, f"flight {value}")
        print_info(output.strip())
    else:
        output = send_cmd(dev, "flight")
        print_info(f"Flight State: {output.strip()}")
