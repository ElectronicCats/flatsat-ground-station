"""Send a raw shell command to the FlatSat console."""

from cli.session import send_cmd

NAME = "cmd"
NEEDS_DEVICE = True


def add_parser(subparsers):
    p = subparsers.add_parser(NAME, help="Send a raw shell command to the FlatSat console.")
    p.add_argument("raw", help="The raw command string to execute")


def run(args, dev):
    output = send_cmd(dev, args.raw)
    if output:
        print(output.strip())
