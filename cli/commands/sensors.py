"""Read live telemetry data from onboard sensors."""

import click

from cli.session import send_cmd, with_device
from cli.ui.output import print_error, print_response, print_title


@click.command("sensors")
@with_device
def sensors(dev):
    """Read live telemetry data from BME280 and LIS2DH sensors"""
    print_title("TELEMETRY SENSORS")
    output = send_cmd(dev, "sensors")
    if output:
        print_response(output.strip())
    else:
        print_error("Failed to retrieve sensor values.")
