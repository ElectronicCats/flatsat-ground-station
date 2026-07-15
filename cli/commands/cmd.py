"""Send a raw shell command to the FlatSat console."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_response


@click.command("cmd")
@click.argument("raw")
@with_device
def cmd(dev, raw):
    """Send a raw shell command to the FlatSat console

    \b
        flatsat cmd "lora_config"
    """
    output = send_cmd(dev, raw)
    if output:
        print_response(output.strip())
