"""Reboot the board (forces it into BOOTSEL mode)."""

import click

from cli.session import with_device
from cli.ui.output import print_info, print_success


@click.command("reboot")
@with_device
def reboot(dev):
    """Reboot the board into the BOOTSEL bootloader"""
    print_info("Rebooting device into BOOTSEL bootloader mode...")
    dev.send_shell_command("reboot")
    print_success("Command sent. Device should disconnect shortly.")
