"""Read live telemetry data from onboard sensors."""

from cli.session import send_cmd
from cli.ui.banner import print_title

NAME = "sensors"
NEEDS_DEVICE = True


def add_parser(subparsers):
    subparsers.add_parser(NAME, help="Read live telemetry data from BME280 and LIS2DH sensors.")


def run(args, dev):
    print_title("TELEMETRY SENSORS")
    output = send_cmd(dev, "sensors")
    if output:
        print(output.strip())
    else:
        print("[-] Failed to retrieve sensor values.")
