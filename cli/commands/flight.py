"""Get or set flight operational state.

Sends the `flight <state>` shell command directly to the connected board, so
this targets the satellite when it is plugged in over USB. Commanding a remote
satellite over RF from a ground station is not handled here.
"""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_info, print_success

FLIGHT_STATES = ["idle", "nominal", "safe", "debug"]


@click.command("flight")
@click.argument("value", required=False, type=click.Choice(FLIGHT_STATES))
@with_device
def flight(dev, value):
    """Get or set flight operational state (idle, nominal, safe, debug)

    \b
        flatsat flight            # query current flight state
        flatsat flight nominal    # set the connected board to NOMINAL
    """
    if value:
        output = send_cmd(dev, f"flight {value}")
        print_success(f"Flight state set to '{value}': {output.strip() if output else 'OK'}")
    else:
        output = send_cmd(dev, "flight")
        print_info(f"Flight State: {output.strip() if output else '(no response)'}")
