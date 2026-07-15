"""Set custom RGB color on the NeoPixel LED."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info


@click.command("color")
@click.argument("r", type=click.IntRange(0, 255))
@click.argument("g", type=click.IntRange(0, 255))
@click.argument("b", type=click.IntRange(0, 255))
@with_device
def color(dev, r, g, b):
    """Set custom RGB color on the NeoPixel LED

    Each channel takes a value from 0 to 255:

    \b
        flatsat color 255 0 0
    """
    output = send_cmd(dev, f"color {r} {g} {b}")
    print_info(output.strip())
