"""Trigger board LED identification blink."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info, print_success


@click.command("identify")
@with_device
def identify(dev):
    """Trigger board LED identification blink"""
    print_info("Identifying FlatSat board (blinking LEDs)...")
    send_cmd(dev, "identify")
    
    # Keep the port open for the duration of the 2.0-second blink sequence to prevent Windows 11 reset interruption
    import time
    time.sleep(2.2)
    print_success("LED identification sequence completed.")
