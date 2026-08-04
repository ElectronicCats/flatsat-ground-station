"""Get or set workshop security/difficulty level."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info


@click.command("difficulty")
@click.argument("value", required=False, type=click.IntRange(1, 3))
@with_device
def difficulty(dev, value):
    """Get or set workshop security/difficulty level"""
    if value is not None:
        output = send_cmd(dev, f"difficulty {value}")
        print_info(output.strip() if output else f"Security Level set to {value}")
    else:
        output = send_cmd(dev, "difficulty")
        print_info(f"Security Level: {output.strip() if output else '(no response)'}")
