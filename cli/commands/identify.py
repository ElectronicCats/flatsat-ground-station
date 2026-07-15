"""Trigger board LED identification blink."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info, print_success


@click.command("identify")
@with_device
def identify(dev):
    """Trigger board LED identification blink"""
    print_info("Identifying FlatSat board (blinking LEDs)...")
    output = send_cmd(dev, "identify")
    if output:
        print_success(output.strip())
