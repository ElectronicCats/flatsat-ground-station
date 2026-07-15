"""Get or set flight operational state."""

from cli.session import send_cmd

NAME = "flight"
NEEDS_DEVICE = True


def add_parser(subparsers):
    p = subparsers.add_parser(NAME, help="Get or set flight operational state.")
    p.add_argument("value", nargs="?", choices=["safe", "nominal", "idle", "debug"], help="Operational state")


def run(args, dev):
    if args.value:
        output = send_cmd(dev, f"flight {args.value}")
        print(f"[*] {output.strip()}")
    else:
        output = send_cmd(dev, "flight")
        print(f"[*] Flight State: {output.strip()}")
