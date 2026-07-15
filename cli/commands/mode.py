"""Get or set satellite operation mode."""

from cli.session import send_cmd

NAME = "mode"
NEEDS_DEVICE = True


def add_parser(subparsers):
    p = subparsers.add_parser(NAME, help="Get or set satellite operation mode.")
    p.add_argument("value", nargs="?", choices=["gs", "sat", "tinygs"], help="Target mode")


def run(args, dev):
    if args.value:
        output = send_cmd(dev, f"mode {args.value}")
        print(f"[*] {output.strip()}")
    else:
        output = send_cmd(dev, "status")
        # Parse active mode from status response
        print(f"[*] Current status info: {output.strip()}")
