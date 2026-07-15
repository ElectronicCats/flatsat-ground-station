"""Read system status and firmware information."""

from cli.session import send_cmd
from cli.ui.banner import print_title

NAME = "status"
NEEDS_DEVICE = True


def add_parser(subparsers):
    subparsers.add_parser(NAME, help="Read system status and firmware information.")


def run(args, dev):
    print_title("SYSTEM STATUS")
    fw_version = send_cmd(dev, "fw_version")
    status = send_cmd(dev, "status")
    if fw_version:
        print(fw_version.strip())
    if status:
        print(status.strip())
